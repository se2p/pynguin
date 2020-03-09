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
from typing import Type, List, Dict, Optional, Any, Union

import pynguin.testcase.statements.statement as stmt
import pynguin.testcase.testcase as tc
import pynguin.testcase.variable.variablereference as vr
import pynguin.testcase.variable.variablereferenceimpl as vri
import pynguin.testcase.statements.statementvisitor as sv
import pynguin.testcase.statements.primitivestatements as prim
import pynguin.configuration as config
from pynguin.utils import randomness
from pynguin.utils.generic.genericaccessibleobject import (
    GenericConstructor,
    GenericMethod,
    GenericAccessibleObject,
    GenericFunction,
)


class ParametrizedStatement(stmt.Statement, metaclass=ABCMeta):  # pylint: disable=W0223
    """
    An abstract statement that has parameters.
    Superclass for e.g., method or constructor statement.
    """

    # pylint: disable=too-many-arguments
    def __init__(
        self,
        test_case: tc.TestCase,
        return_type: Optional[Type] = None,
        args: Optional[List[vr.VariableReference]] = None,
        kwargs: Optional[Dict[str, vr.VariableReference]] = None,
    ):
        """
        Create a new statement with parameters.

        :param test_case: the containing test case.
        :param return_type: the return type.
        :param args: the positional parameters.
        :param kwargs: the keyword parameters.
        """
        super().__init__(test_case, vri.VariableReferenceImpl(test_case, return_type))
        self._args = args if args else []
        self._kwargs = kwargs if kwargs else {}

    @property
    def args(self) -> List[vr.VariableReference]:
        """The positional parameters used in this statement."""
        return self._args

    @args.setter
    def args(self, args: List[vr.VariableReference]):
        self._args = args

    @property
    def kwargs(self) -> Dict[str, vr.VariableReference]:
        """The keyword parameters used in this statement."""
        return self._kwargs

    @kwargs.setter
    def kwargs(self, kwargs: Dict[str, vr.VariableReference]):
        self._kwargs = kwargs

    def _clone_args(
        self, new_test_case: tc.TestCase, offset: int = 0
    ) -> List[vr.VariableReference]:
        """
        Small helper method, to clone the args into a new test case.
        :param new_test_case: The new test case in which the params are used.
        :param offset: Offset when cloning into a non empty test case.
        """
        return [par.clone(new_test_case, offset) for par in self._args]

    def _clone_kwargs(
        self, new_test_case: tc.TestCase, offset: int = 0
    ) -> Dict[str, vr.VariableReference]:
        """
        Small helper method, to clone the args into a new test case.
        :param new_test_case: The new test case in which the params are used.
        :param offset: Offset when cloning into a non empty test case.
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
        """
        Returns the amount of mutable parameters.
        """
        return len(self.args) + len(self.kwargs)

    # pylint: disable=unused-argument,no-self-use
    def _mutate_special_parameters(self, p_per_param: float) -> bool:
        """
        Overwrite this method to mutate any parameter, which is not in arg or kwargs.
        e.g., the callee in an instance method call.
        """
        return False

    def _mutate_parameters(self, p_per_param: float) -> bool:
        """
        Mutates args and kwargs with the given probability.
        :param p_per_param: The probability for one parameter to be mutated.
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
        """
        Replace the given parameter with another one that also fits the parameter type.
        :return True, if the parameter was mutated.
        """
        to_mutate = self._get_argument(arg)
        possible_replacements = self.test_case.get_objects(
            to_mutate.variable_type, self.get_position()
        )

        if to_mutate in possible_replacements:
            possible_replacements.remove(to_mutate)
        if self.return_value in possible_replacements:
            possible_replacements.remove(self.return_value)
        # TODO(fk) handle none stuff
        copy: Optional[stmt.Statement] = None

        # Consider duplicating an existing statement/variable.
        if self._param_count_of_type(to_mutate.variable_type) > len(
            possible_replacements
        ):
            original_param_source = self.test_case.get_statement(
                to_mutate.get_statement_position()
            )
            copy = original_param_source.clone(self.test_case)
            if isinstance(copy, prim.PrimitiveStatement):
                copy.delta()
            possible_replacements.append(copy.return_value)

        if len(possible_replacements) == 0:
            return False

        replacement = randomness.choice(possible_replacements)
        if copy and replacement is copy.return_value:
            self.test_case.add_statement(copy, self.get_position())

        self._replace_argument(arg, replacement)
        return True

    def _param_count_of_type(self, type_: Optional[Type]) -> int:
        """
        Return the number of parameters that have the specified type.
        :param type_: The type, whose occurrences should be counted.
        :return: The number of occurrences.
        """
        count = 0
        if not type_:
            return 0
        for var_ref in self.args:
            if var_ref.variable_type == type_:
                count += 1
        for _, var_ref in self.kwargs.items():
            if var_ref.variable_type == type_:
                count += 1
        return count

    def _get_argument(self, arg: Union[int, str]) -> vr.VariableReference:
        """Returns the arg or kwarg, depending on the parameter type."""
        if isinstance(arg, int):
            return self.args[arg]
        return self.kwargs[arg]

    def _replace_argument(
        self, arg: Union[int, str], new_argument: vr.VariableReference
    ):
        """Replace the arg or kwarg, depending on the parameter type."""
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

    def __init__(
        self,
        test_case: tc.TestCase,
        constructor: GenericConstructor,
        args: Optional[List[vr.VariableReference]] = None,
        kwargs: Optional[Dict[str, vr.VariableReference]] = None,
    ):
        super().__init__(test_case, constructor.generated_type(), args, kwargs)
        self._constructor = constructor

    def clone(self, test_case: tc.TestCase, offset: int = 0) -> stmt.Statement:
        return ConstructorStatement(
            test_case,
            self._constructor,
            self._clone_args(test_case, offset),
            self._clone_kwargs(test_case, offset),
        )

    def accept(self, visitor: sv.StatementVisitor) -> None:
        visitor.visit_constructor_statement(self)

    def accessible_object(self) -> Optional[GenericAccessibleObject]:
        return self._constructor

    @property
    def constructor(self) -> GenericConstructor:
        """The used constructor."""
        return self._constructor


class MethodStatement(ParametrizedStatement):
    """A statement that calls a method on an object."""

    # pylint: disable=too-many-arguments
    def __init__(
        self,
        test_case: tc.TestCase,
        method: GenericMethod,
        callee: vr.VariableReference,
        args: Optional[List[vr.VariableReference]] = None,
        kwargs: Optional[Dict[str, vr.VariableReference]] = None,
    ):
        """
        Create new method statement.
        :param test_case: The containing test case
        :param callee: the object on which the method is called
        :param args: the positional arguments
        :param kwargs: the keyword arguments
        """
        super().__init__(
            test_case, method.generated_type(), args, kwargs,
        )
        self._method = method
        self._callee = callee

    def accessible_object(self) -> Optional[GenericAccessibleObject]:
        return self._method

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

    @property
    def method(self) -> GenericMethod:
        """The used method."""
        return self._method

    @property
    def callee(self) -> vr.VariableReference:
        """Provides the variable on which the method is invoked."""
        return self._callee

    @callee.setter
    def callee(self, new_callee: vr.VariableReference) -> None:
        """Set new callee on which the method is invoked."""
        self._callee = new_callee

    def clone(self, test_case: tc.TestCase, offset: int = 0) -> stmt.Statement:
        return MethodStatement(
            test_case,
            self._method,
            self._callee.clone(test_case, offset),
            self._clone_args(test_case, offset),
            self._clone_kwargs(test_case, offset),
        )

    def accept(self, visitor: sv.StatementVisitor) -> None:
        visitor.visit_method_statement(self)


class FunctionStatement(ParametrizedStatement):
    """A statement that calls a function."""

    # pylint: disable=too-many-arguments
    def __init__(
        self,
        test_case: tc.TestCase,
        function: GenericFunction,
        args: Optional[List[vr.VariableReference]] = None,
        kwargs: Optional[Dict[str, vr.VariableReference]] = None,
    ) -> None:
        """

        """
        super().__init__(test_case, function.generated_type(), args, kwargs)
        self._function = function

    def accessible_object(self) -> Optional[GenericAccessibleObject]:
        return self._function

    @property
    def function(self) -> GenericFunction:
        """The used function."""
        return self._function

    def clone(self, test_case: tc.TestCase, offset: int = 0) -> stmt.Statement:
        return FunctionStatement(
            test_case,
            self._function,
            self._clone_args(test_case, offset),
            self._clone_kwargs(test_case, offset),
        )

    def accept(self, visitor: sv.StatementVisitor) -> None:
        visitor.visit_function_statement(self)

    def __repr__(self) -> str:
        return (
            f"FunctionStatement({self._test_case}, "
            f"{self._function}, {self._return_value.variable_type}, "
            f"args={self._args}, kwargs={self._kwargs})"
        )

    def __str__(self) -> str:
        return (
            f"{self._function}(args={self._args}, kwargs={self._kwargs}) -> "
            f"{self._return_value.variable_type}"
        )
