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
from typing import Type, List, Dict, Optional, Any

import pynguin.testcase.statements.statement as stmt
import pynguin.testcase.testcase as tc
import pynguin.testcase.variable.variablereference as vr
import pynguin.testcase.variable.variablereferenceimpl as vri
import pynguin.testcase.statements.statementvisitor as sv
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

    def mutate(self) -> bool:
        raise Exception("Implement me")

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

    def mutate(self) -> bool:
        raise Exception("Implement me")

    @property
    def method(self) -> GenericMethod:
        """The used method."""
        return self._method

    @property
    def callee(self) -> vr.VariableReference:
        """Provides the variable on which the method is invoked."""
        return self._callee

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

    def mutate(self) -> bool:
        raise Exception("Implement me")

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
