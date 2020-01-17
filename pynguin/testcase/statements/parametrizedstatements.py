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
from inspect import Signature
from typing import Type, List

import pynguin.testcase.statements.statement as stmt
import pynguin.testcase.testcase as tc
import pynguin.testcase.variable.variablereference as vr
import pynguin.testcase.variable.variablereferenceimpl as vri


class EntityWithParametersStatement(
    stmt.Statement, metaclass=ABCMeta
):  # pylint: disable=W0223
    """An abstract statement that has parameters. Superclass for e.g., method or constructor."""

    def __init__(
        self,
        test_case: tc.TestCase,
        return_type: Type,
        parameters: List[vr.VariableReference],
    ):
        """
        Create a new statement with parameters.

        :param test_case: the containing test case.
        :param return_type: the return type.
        :param parameters: the parameters.
        """
        super().__init__(test_case, vri.VariableReferenceImpl(test_case, return_type))
        self._parameters = parameters

    @property
    def parameters(self):
        """The parameters used in this statement."""
        return self._parameters

    @parameters.setter
    def parameters(self, parameters: List[vr.VariableReference]):
        self._parameters = parameters


class ConstructorStatement(EntityWithParametersStatement):
    """A statement that constructs an object"""

    def __init__(
        self,
        test_case: tc.TestCase,
        constructor: Signature,  # TODO Merge signature and type into a wrapper?
        parameters: List[vr.VariableReference],
    ):
        super().__init__(test_case, constructor.return_annotation, parameters)
        # TODO: return_annotation is wrong, because a constructor returns None.
        self._constructor = constructor

    def clone(self, test_case: tc.TestCase) -> stmt.Statement:
        pass


class MethodStatement(EntityWithParametersStatement):
    """A statement that calls a method on an object"""

    def __init__(
        self,
        test_case: tc.TestCase,
        method: Signature,  # TODO Merge signature and type into a wrapper?
        callee: vr.VariableReference,
        parameters: List[vr.VariableReference],
    ):
        super().__init__(test_case, method.return_annotation, parameters)
        self._method = method
        self._callee = callee

    def clone(self, test_case: tc.TestCase) -> stmt.Statement:
        pass
