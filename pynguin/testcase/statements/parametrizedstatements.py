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
from typing import Type, List, Any

import typing

import pynguin.testcase.statements.statement as stmt
import pynguin.testcase.testcase as tc
import pynguin.testcase.variable.variablereference as vr
import pynguin.testcase.variable.variablereferenceimpl as vri
import pynguin.testcase.statements.statementvisitor as sv
from pynguin.typeinference.strategy import InferredMethodType


class ParametrizedStatement(stmt.Statement, metaclass=ABCMeta):  # pylint: disable=W0223
    """
    An abstract statement that has parameters.
    Superclass for e.g., method or constructor statement.
    """

    def __init__(
        self,
        test_case: tc.TestCase,
        method_type: InferredMethodType,
        return_type: Type,
        parameters: List[vr.VariableReference],
    ):
        """
        Create a new statement with parameters.

        :param test_case: the containing test case.
        :param method_type: the inferred method type.
        :param return_type: the return type.
        :param parameters: the parameters.
        """
        super().__init__(test_case, vri.VariableReferenceImpl(test_case, return_type))
        self._parameters = parameters
        self._method_type = method_type

    @property
    def parameters(self):
        """The parameters used in this statement."""
        return self._parameters

    @parameters.setter
    def parameters(self, parameters: List[vr.VariableReference]):
        self._parameters = parameters

    def _clone_params(self, new_test_case: tc.TestCase) -> List[vr.VariableReference]:
        """
        Small helper method, to clone the parameters into a new test case.
        :param new_test_case: The new test case in which the params are used.
        """
        new_params = []
        for par in self._parameters:
            new_params.append(par.clone(new_test_case))
        return new_params


class ConstructorStatement(ParametrizedStatement):
    """A statement that constructs an object."""

    def clone(self, test_case: tc.TestCase) -> stmt.Statement:
        return ConstructorStatement(
            test_case,
            self._method_type,
            self.return_value.variable_type,
            self._clone_params(test_case),
        )

    def accept(self, visitor: sv.StatementVisitor) -> None:
        visitor.visit_constructor_statement(self)


class MethodStatement(ParametrizedStatement):
    """A statement that calls a method on an object."""

    def __init__(
        self,
        test_case: tc.TestCase,
        method_type: InferredMethodType,
        callee: vr.VariableReference,
        parameters: List[vr.VariableReference],
    ):
        super().__init__(
            test_case,
            method_type,
            typing.Union[Any]
            if method_type.return_type is None
            else method_type.return_type,
            parameters,
        )
        self._callee = callee

    def clone(self, test_case: tc.TestCase) -> stmt.Statement:
        return MethodStatement(
            test_case,
            self._method_type,
            self._callee.clone(test_case),
            self._clone_params(test_case),
        )

    def accept(self, visitor: sv.StatementVisitor) -> None:
        visitor.visit_method_statement(self)
