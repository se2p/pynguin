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
from __future__ import annotations
from abc import ABCMeta, abstractmethod
from typing import Type

import pynguin.testcase.testcase as tc  # pylint: disable=cyclic-import


class VariableReference(metaclass=ABCMeta):
    """Represents a variable in a test case."""

    def __init__(self, test_case: tc.TestCase, variable_type: Type) -> None:
        self._variable_type = variable_type
        self._test_case = test_case

    @abstractmethod
    def clone(self, test_case: tc.TestCase) -> VariableReference:
        """Provides a deep copy of the current variable.
        :param test_case: the new test case in which this clone will be used.

        :return: A deep copy of the current variable
        """

    @property
    def variable_type(self) -> Type:
        """Provides the type of this variable.

        :return: The type of this variable
        """
        return self._variable_type

    @variable_type.setter
    def variable_type(self, variable_type: Type) -> None:
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
