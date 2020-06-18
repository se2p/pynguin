# This file is part of Pynguin.
#
# Pynguin is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Pynguin is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Pynguin.  If not, see <https://www.gnu.org/licenses/>.
"""Provides an abstract class for statements that require parameters"""
from abc import ABCMeta
from typing import Any, Dict, List, Optional, Set, Type, Union, cast

import pynguin.configuration as config
import pynguin.testcase.statements.primitivestatements as prim
import pynguin.testcase.statements.statement as stmt
import pynguin.testcase.statements.statementvisitor as sv
import pynguin.testcase.testcase as tc
import pynguin.testcase.variable.variablereference as vr
import pynguin.testcase.variable.variablereferenceimpl as vri
from pynguin.utils import randomness
from pynguin.utils.generic.genericaccessibleobject import (
    GenericCallableAccessibleObject,
    GenericConstructor,
    GenericFunction,
    GenericMethod,
)
from pynguin.utils.type_utils import is_assignable_to


class ParametrizedStatement(stmt.Statement, metaclass=ABCMeta):  # pylint: disable=W0223
    """An abstract statement that has parameters.

    Superclass for e.g., method or constructor statement.
    """

    # pylint: disable=too-many-arguments
    def __init__(
        self,
        test_case: tc.TestCase,
        generic_callable: GenericCallableAccessibleObject,
        args: Optional[List[vr.VariableReference]] = None,
        kwargs: Optional[Dict[str, vr.VariableReference]] = None,
    ):
        """
        Create a new statement with parameters.

        Args:
            test_case: the containing test case.
            generic_callable: the callable
            args: the positional parameters.
            kwargs: the keyword parameters.
        """
        super().__init__(
            test_case,
            vri.VariableReferenceImpl(test_case, generic_callable.generated_type()),
        )
        self._generic_callable = generic_callable
        self._args = args if args else []
        self._kwargs = kwargs if kwargs else {}

    @property
    def args(self) -> List[vr.VariableReference]:
        """The positional parameters used in this statement.

        Returns:
            A list of positional parameters
        """
        return self._args

    @args.setter
    def args(self, args: List[vr.VariableReference]):
        self._args = args

    @property
    def kwargs(self) -> Dict[str, vr.VariableReference]:
        """The keyword parameters used in this statement.

        Returns:
            The dictionary of keyword parameters
        """
        return self._kwargs

    @kwargs.setter
    def kwargs(self, kwargs: Dict[str, vr.VariableReference]):
        self._kwargs = kwargs

    def get_variable_references(self) -> Set[vr.VariableReference]:
        references = set()
        references.add(self.return_value)
        references.update(self.args)
        references.update(self.kwargs.values())
        return references

    def replace(self, old: vr.VariableReference, new: vr.VariableReference) -> None:
        if self.return_value == old:
            self.return_value = new
        self._args = [new if arg == old else arg for arg in self._args]
        for key, value in self._kwargs.items():
            if value == old:
                self._kwargs[key] = new

    def _clone_args(
        self, new_test_case: tc.TestCase, offset: int = 0
    ) -> List[vr.VariableReference]:
        """Small helper method, to clone the args into a new test case.

        Args:
            new_test_case: The new test case in which the params are used.
            offset: Offset when cloning into a non empty test case.

        Returns:
            A list of the arguments references
        """
        return [par.clone(new_test_case, offset) for par in self._args]

    def _clone_kwargs(
        self, new_test_case: tc.TestCase, offset: int = 0
    ) -> Dict[str, vr.VariableReference]:
        """Small helper method, to clone the args into a new test case.

        Args:
            new_test_case: The new test case in which the params are used.
            offset: Offset when cloning into a non empty test case.

        Returns:
            A dictionary of key-value argument references
        """
        new_kw_args = {}
        for name, var in self._kwargs.items():
            new_kw_args[name] = var.clone(new_test_case, offset)
        return new_kw_args

    def mutate(self) -> bool:
        if randomness.next_float() >= config.INSTANCE.change_parameter_probability:
            return False

        changed = False
        mutable_param_count = self._mutable_argument_count()
        if mutable_param_count > 0:
            p_per_param = 1.0 / mutable_param_count
            changed |= self._mutate_special_parameters(p_per_param)
            changed |= self._mutate_parameters(p_per_param)
        return changed

    def _mutable_argument_count(self) -> int:
        """Returns the amount of mutable parameters.

        Returns:
            The amount of mutable parameters
        """
        return len(self.args) + len(self.kwargs)

    # pylint: disable=unused-argument,no-self-use
    def _mutate_special_parameters(self, p_per_param: float) -> bool:
        """Overwrite this method to mutate any parameter, which is not in arg or kwargs.
        e.g., the callee in an instance method call.

        Args:
            p_per_param: the probability per parameter

        Returns:
            Whether or not mutation should be applied
        """
        return False

    def _mutate_parameters(self, p_per_param: float) -> bool:
        """Mutates args and kwargs with the given probability.

        Args:
            p_per_param: The probability for one parameter to be mutated.

        Returns:
            Whether or not mutation changed anything
        """
        changed = False
        for arg in range(len(self.args)):
            if randomness.next_float() < p_per_param:
                changed |= self._mutate_parameter(arg)
        for kwarg in self.kwargs.keys():
            if randomness.next_float() < p_per_param:
                changed |= self._mutate_parameter(kwarg)
        return changed

    def _mutate_parameter(self, arg: Union[int, str]) -> bool:
        """Replace the given parameter with another one that also fits the parameter
        type.

        Args:
            arg: the parameter

        Returns:
            True, if the parameter was mutated.
        """
        to_mutate = self._get_argument(arg)
        param_type = self._get_parameter_type(arg)
        possible_replacements = self.test_case.get_objects(
            param_type, self.get_position()
        )

        if to_mutate in possible_replacements:
            possible_replacements.remove(to_mutate)

        # Consider duplicating an existing statement/variable.
        copy: Optional[stmt.Statement] = None
        if self._param_count_of_type(param_type) > len(possible_replacements) + 1:
            original_param_source = self.test_case.get_statement(
                to_mutate.get_statement_position()
            )
            copy = original_param_source.clone(self.test_case)
            copy.mutate()
            possible_replacements.append(copy.return_value)

        # TODO(fk) Use param_type instead of to_mutate.variable_type,
        # to make the selection broader, but this requires access to
        # the test cluster, to select a concrete type.
        # Using None as parameter value is also a possibility.
        none_statement = prim.NoneStatement(self.test_case, to_mutate.variable_type)
        possible_replacements.append(none_statement.return_value)

        replacement = randomness.choice(possible_replacements)

        if copy and replacement is copy.return_value:
            # The chosen replacement is a copy, so we have to add it to the test case.
            self.test_case.add_statement(copy, self.get_position())
        elif replacement is none_statement.return_value:
            # The chosen replacement is a none statement, so we have to add it to the test case.
            self.test_case.add_statement(none_statement, self.get_position())

        self._replace_argument(arg, replacement)
        return True

    def _param_count_of_type(self, type_: Optional[Type]) -> int:
        """Return the number of parameters that have the specified type.

        Args:
            type_: The type, whose occurrences should be counted.

        Returns:
            The number of occurrences.
        """
        count = 0
        if not type_:
            return 0
        for var_ref in self.args:
            if is_assignable_to(var_ref.variable_type, type_):
                count += 1
        for _, var_ref in self.kwargs.items():
            if is_assignable_to(var_ref.variable_type, type_):
                count += 1
        return count

    def _get_parameter_type(self, arg: Union[int, str]) -> Optional[Type]:
        parameters = self._generic_callable.inferred_signature.parameters
        if isinstance(arg, int):
            # As of Python 3.7, Dictionaries preserve insertion order.
            # So we can access the values by index.
            return list(parameters.values())[arg]
        return parameters[arg]

    def _get_argument(self, arg: Union[int, str]) -> vr.VariableReference:
        if isinstance(arg, int):
            return self.args[arg]
        return self.kwargs[arg]

    def _replace_argument(
        self, arg: Union[int, str], new_argument: vr.VariableReference
    ):
        if isinstance(arg, int):
            self.args[arg] = new_argument
        else:
            self.kwargs[arg] = new_argument

    def __hash__(self) -> int:
        return (
            31
            + 17 * hash(self._return_value)
            + 17 * hash(frozenset(self._args))
            + 17 * hash(frozenset(self._kwargs.items()))
        )

    def __eq__(self, other: Any) -> bool:
        if self is other:
            return True
        if not isinstance(other, ParametrizedStatement):
            return False
        return (
            self._return_value == other._return_value
            and self._args == other._args
            and self._kwargs == other._kwargs
        )


class ConstructorStatement(ParametrizedStatement):
    """A statement that constructs an object."""

    def clone(self, test_case: tc.TestCase, offset: int = 0) -> stmt.Statement:
        return ConstructorStatement(
            test_case,
            self.accessible_object(),
            self._clone_args(test_case, offset),
            self._clone_kwargs(test_case, offset),
        )

    def accept(self, visitor: sv.StatementVisitor) -> None:
        visitor.visit_constructor_statement(self)

    def accessible_object(self) -> GenericConstructor:
        """The used constructor.

        Returns:
            The used constructor
        """
        return cast(GenericConstructor, self._generic_callable)

    def __repr__(self) -> str:
        return (
            f"ConstructorStatement({self._test_case}, "
            f"{self._generic_callable}(args={self._args}, kwargs={self._kwargs})"
        )

    def __str__(self) -> str:
        return f"{self._generic_callable}(args={self._args}, kwargs={self._kwargs}) -> None"


class MethodStatement(ParametrizedStatement):
    """A statement that calls a method on an object."""

    # pylint: disable=too-many-arguments
    def __init__(
        self,
        test_case: tc.TestCase,
        generic_callable: GenericMethod,
        callee: vr.VariableReference,
        args: Optional[List[vr.VariableReference]] = None,
        kwargs: Optional[Dict[str, vr.VariableReference]] = None,
    ):
        """Create new method statement.

        Args:
            test_case: The containing test case
            generic_callable: The generic callable method
            callee: the object on which the method is called
            args: the positional arguments
            kwargs: the keyword arguments
        """
        super().__init__(
            test_case, generic_callable, args, kwargs,
        )
        self._callee = callee

    def accessible_object(self) -> GenericMethod:
        """The used method.

        Returns:
            The used method
        """
        return cast(GenericMethod, self._generic_callable)

    def _mutable_argument_count(self) -> int:
        # We add +1 to the count, because the callee itself can also be mutated.
        return super()._mutable_argument_count() + 1

    def _mutate_special_parameters(self, p_per_param: float) -> bool:
        # We mutate the callee here, as the special parameter.
        if randomness.next_float() < p_per_param:
            callee = self.callee
            objects = self.test_case.get_objects(
                callee.variable_type, self.get_position()
            )
            objects.remove(callee)

            if len(objects) > 0:
                self.callee = randomness.choice(objects)
                return True
        return False

    def get_variable_references(self) -> Set[vr.VariableReference]:
        references = super().get_variable_references()
        references.add(self._callee)
        return references

    def replace(self, old: vr.VariableReference, new: vr.VariableReference) -> None:
        super().replace(old, new)
        if self._callee == old:
            self._callee = new

    @property
    def callee(self) -> vr.VariableReference:
        """Provides the variable on which the method is invoked.

        Returns:
            The variable on which the method is invoked
        """
        return self._callee

    @callee.setter
    def callee(self, new_callee: vr.VariableReference) -> None:
        """Set new callee on which the method is invoked.

        Args:
            new_callee: Sets a new callee
        """
        self._callee = new_callee

    def clone(self, test_case: tc.TestCase, offset: int = 0) -> stmt.Statement:
        return MethodStatement(
            test_case,
            self.accessible_object(),
            self._callee.clone(test_case, offset),
            self._clone_args(test_case, offset),
            self._clone_kwargs(test_case, offset),
        )

    def accept(self, visitor: sv.StatementVisitor) -> None:
        visitor.visit_method_statement(self)

    def __repr__(self) -> str:
        return (
            f"MethodStatement({self._test_case}, "
            f"{self._generic_callable}, {self._callee.variable_type}, "
            f"args={self._args}, kwargs={self._kwargs})"
        )

    def __str__(self) -> str:
        return (
            f"{self._generic_callable}(args={self._args}, kwargs={self._kwargs}) -> "
            f"{self._generic_callable.generated_type()}"
        )


class FunctionStatement(ParametrizedStatement):
    """A statement that calls a function."""

    def accessible_object(self) -> GenericFunction:
        """The used function.

        Returns:
            The used function
        """
        return cast(GenericFunction, self._generic_callable)

    def clone(self, test_case: tc.TestCase, offset: int = 0) -> stmt.Statement:
        return FunctionStatement(
            test_case,
            self.accessible_object(),
            self._clone_args(test_case, offset),
            self._clone_kwargs(test_case, offset),
        )

    def accept(self, visitor: sv.StatementVisitor) -> None:
        visitor.visit_function_statement(self)

    def __repr__(self) -> str:
        return (
            f"FunctionStatement({self._test_case}, "
            f"{self._generic_callable}, {self._return_value.variable_type}, "
            f"args={self._args}, kwargs={self._kwargs})"
        )

    def __str__(self) -> str:
        return (
            f"{self._generic_callable}(args={self._args}, kwargs={self._kwargs}) -> "
            f"{self._return_value.variable_type}"
        )
