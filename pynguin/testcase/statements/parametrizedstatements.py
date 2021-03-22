#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides an abstract class for statements that require parameters"""
from abc import ABCMeta
from typing import Any, Dict, Optional, Set, Type, Union, cast

import pynguin.configuration as config
import pynguin.testcase.statements.primitivestatements as prim
import pynguin.testcase.statements.statement as stmt
import pynguin.testcase.statements.statementvisitor as sv
import pynguin.testcase.testcase as tc
import pynguin.testcase.variable.variablereference as vr
import pynguin.testcase.variable.variablereferenceimpl as vri
from pynguin.typeinference.strategy import InferredSignature
from pynguin.utils import randomness
from pynguin.utils.generic.genericaccessibleobject import (
    GenericCallableAccessibleObject,
    GenericConstructor,
    GenericFunction,
    GenericMethod,
)
from pynguin.utils.type_utils import is_assignable_to, is_optional_parameter


class ParametrizedStatement(stmt.Statement, metaclass=ABCMeta):  # pylint: disable=W0223
    """An abstract statement that has parameters.

    Superclass for e.g., method or constructor statement.
    """

    # pylint: disable=too-many-arguments
    def __init__(
        self,
        test_case: tc.TestCase,
        generic_callable: GenericCallableAccessibleObject,
        args: Optional[Dict[str, vr.VariableReference]] = None,
    ):
        """
        Create a new statement with parameters.

        Args:
            test_case: the containing test case.
            generic_callable: the callable
            args: A map of parameter names to their values.
        """
        super().__init__(
            test_case,
            vri.VariableReferenceImpl(test_case, generic_callable.generated_type()),
        )
        self._generic_callable = generic_callable
        self._args = args if args else {}

    @property
    def args(self) -> Dict[str, vr.VariableReference]:
        """The dictionary mapping parameter names to the used values.

        Returns:
            A dict mapping parameter names to their values.
        """
        return self._args

    @args.setter
    def args(self, args: Dict[str, vr.VariableReference]):
        self._args = args

    def get_variable_references(self) -> Set[vr.VariableReference]:
        references = set()
        references.add(self.ret_val)
        references.update(self.args.values())
        return references

    def replace(self, old: vr.VariableReference, new: vr.VariableReference) -> None:
        if self.ret_val == old:
            self.ret_val = new
        for key, value in self._args.items():
            if value == old:
                self._args[key] = new

    def _clone_args(
        self, new_test_case: tc.TestCase, offset: int = 0
    ) -> Dict[str, vr.VariableReference]:
        """Small helper method, to clone the args into a new test case.

        Args:
            new_test_case: The new test case in which the params are used.
            offset: Offset when cloning into a non empty test case.

        Returns:
            A dictionary of key-value argument references
        """
        new_args = {}
        for name, var in self._args.items():
            new_args[name] = var.clone(new_test_case, offset)
        return new_args

    def mutate(self) -> bool:
        if randomness.next_float() >= config.configuration.change_parameter_probability:
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
        return len(self.args)

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
        for param_name in self._generic_callable.inferred_signature.parameters:
            if randomness.next_float() < p_per_param:
                changed |= self._mutate_parameter(
                    param_name, self._generic_callable.inferred_signature
                )

        return changed

    def _mutate_parameter(self, param_name: str, inf_sig: InferredSignature) -> bool:
        """Replace the given parameter with another one that also fits the parameter
        type.

        Args:
            param_name: the name of the parameter that should be mutated.

        Returns:
            True, if the parameter was mutated.
        """
        current = self._args.get(param_name, None)
        param_type = inf_sig.parameters[param_name]
        possible_replacements = self.test_case.get_objects(
            param_type, self.get_position()
        )

        # Param has to be optional, otherwise it would be set.
        if current is None:
            # Create value for currently unset parameter.
            if (
                randomness.next_float()
                > config.configuration.skip_optional_parameter_probability
            ):
                if len(possible_replacements) > 0:
                    self._args[param_name] = randomness.choice(possible_replacements)
                    return True
            return False

        if (
            is_optional_parameter(inf_sig, param_name)
            and randomness.next_float()
            < config.configuration.skip_optional_parameter_probability
        ):
            # unset parameters that are not necessary with a certain probability,
            # e.g., if they have default value or are *args, **kwargs.
            self._args.pop(param_name)

        if current in possible_replacements:
            possible_replacements.remove(current)

        # Consider duplicating an existing statement/variable.
        copy: Optional[stmt.Statement] = None
        if self._param_count_of_type(param_type) > len(possible_replacements) + 1:
            original_param_source = self.test_case.get_statement(
                current.get_statement_position()
            )
            copy = original_param_source.clone(self.test_case)
            copy.mutate()
            possible_replacements.append(copy.ret_val)

        # TODO(fk) Use param_type instead of to_mutate.variable_type,
        # to make the selection broader, but this requires access to
        # the test cluster, to select a concrete type.
        # Using None as parameter value is also a possibility.
        none_statement = prim.NoneStatement(self.test_case, current.variable_type)
        possible_replacements.append(none_statement.ret_val)

        replacement = randomness.choice(possible_replacements)

        if copy and replacement is copy.ret_val:
            # The chosen replacement is a copy, so we have to add it to the test case.
            self.test_case.add_statement(copy, self.get_position())
        elif replacement is none_statement.ret_val:
            # The chosen replacement is a none statement, so we have to add it to the
            # test case.
            self.test_case.add_statement(none_statement, self.get_position())

        self._args[param_name] = replacement
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
        for _, var_ref in self.args.items():
            if is_assignable_to(var_ref.variable_type, type_):
                count += 1
        return count

    def _get_parameter_type(self, arg: Union[int, str]) -> Optional[Type]:
        parameters = self._generic_callable.inferred_signature.parameters
        if isinstance(arg, int):

            return list(parameters.values())[arg]
        return parameters[arg]

    def __hash__(self) -> int:
        return 31 + 17 * hash(self._ret_val) + 17 * hash(frozenset(self._args.items()))

    def __eq__(self, other: Any) -> bool:
        if self is other:
            return True
        if not isinstance(other, ParametrizedStatement):
            return False
        return self._ret_val == other._ret_val and self._args == other._args


class ConstructorStatement(ParametrizedStatement):
    """A statement that constructs an object."""

    def clone(self, test_case: tc.TestCase, offset: int = 0) -> stmt.Statement:
        return ConstructorStatement(
            test_case, self.accessible_object(), self._clone_args(test_case, offset)
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
            + f"{self._generic_callable}(args={self._args})"
        )

    def __str__(self) -> str:
        return f"{self._generic_callable}(args={self._args})" + "-> None"


class MethodStatement(ParametrizedStatement):
    """A statement that calls a method on an object."""

    # pylint: disable=too-many-arguments
    def __init__(
        self,
        test_case: tc.TestCase,
        generic_callable: GenericMethod,
        callee: vr.VariableReference,
        args: Optional[Dict[str, vr.VariableReference]] = None,
    ):
        """Create new method statement.

        Args:
            test_case: The containing test case
            generic_callable: The generic callable method
            callee: the object on which the method is called
            args: the arguments
        """
        super().__init__(test_case, generic_callable, args)
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
        )

    def accept(self, visitor: sv.StatementVisitor) -> None:
        visitor.visit_method_statement(self)

    def __repr__(self) -> str:
        return (
            f"MethodStatement({self._test_case}, "
            f"{self._generic_callable}, {self._callee.variable_type}, "
            f"args={self._args})"
        )

    def __str__(self) -> str:
        return (
            f"{self._generic_callable}(args={self._args}) -> "
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
            test_case, self.accessible_object(), self._clone_args(test_case, offset)
        )

    def accept(self, visitor: sv.StatementVisitor) -> None:
        visitor.visit_function_statement(self)

    def __repr__(self) -> str:
        return (
            f"FunctionStatement({self._test_case}, "
            f"{self._generic_callable}, {self._ret_val.variable_type}, "
            f"args={self._args})"
        )

    def __str__(self) -> str:
        return (
            f"{self._generic_callable}(args={self._args}) -> "
            + f"{self._ret_val.variable_type}"
        )
