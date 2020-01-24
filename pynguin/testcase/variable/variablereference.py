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
"""Provides a base implementation of a variable in a test case."""
# pylint: disable=cyclic-import
from __future__ import annotations
from abc import ABCMeta, abstractmethod
from typing import Type, Optional

import pynguin.testcase.testcase as tc


class VariableReference(metaclass=ABCMeta):
    """Represents a variable in a test case."""

    def __init__(self, test_case: tc.TestCase, variable_type: Optional[Type]) -> None:
        self._variable_type = variable_type
        self._test_case = test_case

    @abstractmethod
    def clone(self, new_test_case: tc.TestCase) -> VariableReference:
        """
        This method is essential for the whole variable references to work.
        'self' must not be cloned. Instead we have to look for the
        corresponding variable reference in the new test case.
        Actual cloning is only performed on statement level.
        :param new_test_case: the new test case in which this clone will be used.

        :return: The corresponding variable reference of the this variable in the new test case.
        """

    @abstractmethod
    def get_statement_position(self) -> int:
        """
        Provides the position of the statement which defines this variable reference
        in the test case.
        """

    @property
    def variable_type(self) -> Optional[Type]:
        """Provides the type of this variable.

        :return: The type of this variable
        """
        return self._variable_type

    @variable_type.setter
    def variable_type(self, variable_type: Optional[Type]) -> None:
        """Allows to set the type of this variable.

        :param variable_type: The new type of this variable
        """
        self._variable_type = variable_type

    @property
    def test_case(self) -> tc.TestCase:
        """Provides the test case in which this variable reference is used.

        :return: The containing test case
        """
        return self._test_case

    def __repr__(self) -> str:
        return f"VariableReference({self._test_case}, {self._variable_type})"

    def __str__(self) -> str:
        return f"{self._variable_type}"
