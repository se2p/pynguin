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
"""Provides a base implementation of a statement representation."""
# pylint: disable=cyclic-import
from __future__ import annotations

import logging
from abc import ABCMeta, abstractmethod
from typing import Any, Optional

import pynguin.testcase.testcase as tc
import pynguin.testcase.variable.variablereference as vr
import pynguin.testcase.statements.statementvisitor as sv
from pynguin.utils.generic.genericaccessibleobject import GenericAccessibleObject


class Statement(metaclass=ABCMeta):
    """An abstract base class of a statement representation."""

    def __init__(
        self, test_case: tc.TestCase, return_value: vr.VariableReference
    ) -> None:
        self._test_case = test_case
        self._return_value = return_value
        self._logger = logging.getLogger(__name__)

    @property
    def return_value(self) -> vr.VariableReference:
        """Provides the return value of this statement.

        :return: The return value of the statement execution
        """
        return self._return_value

    @return_value.setter
    def return_value(self, reference: vr.VariableReference) -> None:
        """Updates the return value of this statement.

        :param reference: The new return value
        """
        self._return_value = reference

    @property
    def test_case(self) -> tc.TestCase:
        """Provides the test case in which this statement is used.

        :return: The containing test case
        """
        return self._test_case

    @abstractmethod
    def clone(self, test_case: tc.TestCase, offset: int = 0) -> Statement:
        """Provides a deep clone of this statement.
        :param test_case: the new test case in which the clone will be used.
        :param offset: Offset when cloning into a non empty test case.
        :return: A deep clone of this statement
        """

    @abstractmethod
    def accept(self, visitor: sv.StatementVisitor) -> None:
        """Accepts a visitor to visit this statement."""

    @abstractmethod
    def accessible_object(self) -> Optional[GenericAccessibleObject]:
        """Provides the accessible which is used in this statement."""

    @abstractmethod
    def mutate(self) -> bool:
        """
        Mutate this statement.
        :return True, if a mutation happened.
        """

    def get_position(self):
        """Provides the position of this statement in the test case."""
        return self._return_value.get_statement_position()

    def __eq__(self, other: Any) -> bool:
        raise NotImplementedError("You need to override __eq__ for your statement type")

    def __hash__(self) -> int:
        raise NotImplementedError(
            "You need to override __hash__ for your statement type"
        )
