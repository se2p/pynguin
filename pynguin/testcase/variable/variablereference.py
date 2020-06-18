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
from typing import Any, Optional, Type

import pynguin.testcase.testcase as tc
from pynguin.utils import type_utils
from pynguin.utils.type_utils import is_type_unknown


class VariableReference(metaclass=ABCMeta):
    """Represents a variable in a test case."""

    def __init__(self, test_case: tc.TestCase, variable_type: Optional[Type]) -> None:
        self._variable_type = variable_type
        self._test_case = test_case
        self._distance = 0

    @abstractmethod
    def clone(self, new_test_case: tc.TestCase, offset: int = 0) -> VariableReference:
        """This method is essential for the whole variable references to work while
        cloning.

        'self' must not be cloned. Instead we have to look for the
        corresponding variable reference in the new test case.
        Actual cloning is only performed on statement level.

        Args:
            new_test_case: the new test case in which we search for the corresponding
                variable reference.
            offset: Offset must be used when cloning is performed on a test case,
                which already contains statements, i.e., when appending on test case
                onto another. The position of the statement which defines the new
                reference within the new test case will be different, so we have to add
                the offset when searching for the new reference.

        Returns:  # noqa: DAR202
            The corresponding variable reference of this variable in the new test case.
        """

    @abstractmethod
    def get_statement_position(self) -> int:
        """Provides the position of the statement which defines this variable reference
        in the test case.

        Returns:
            The position  # noqa: DAR202
        """

    @property
    def variable_type(self) -> Optional[Type]:
        """Provides the type of this variable.

        Returns:
            The type of this variable
        """
        return self._variable_type

    @variable_type.setter
    def variable_type(self, variable_type: Optional[Type]) -> None:
        """Allows to set the type of this variable.

        Args:
            variable_type: The new type of this variable
        """
        self._variable_type = variable_type

    @property
    def test_case(self) -> tc.TestCase:
        """Provides the test case in which this variable reference is used.

        Returns:
            The containing test case
        """
        return self._test_case

    @property
    def distance(self) -> int:
        """Distance metric used to select variables for mutation based on how close
        they are to the subject under test.

        Returns:
            The distance value
        """
        return self._distance

    @distance.setter
    def distance(self, distance: int) -> None:
        """Set the distance metric.

        Args:
            distance: The new distance value
        """
        self._distance = distance

    def is_primitive(self) -> bool:
        """Does this variable reference represent a primitive type.

        Returns:
            True if the variable is a primitive
        """
        return type_utils.is_primitive_type(self._variable_type)

    def is_none_type(self) -> bool:
        """Is this variable reference of type none, i.e. it does not return anything.

        Returns:
            True if this variable is a none type
        """
        return type_utils.is_none_type(self._variable_type)

    def is_type_unknown(self) -> bool:
        """Is the type of this variable unknown?

        Returns:
            True if this variable has unknown type
        """
        return is_type_unknown(self._variable_type)

    def __repr__(self) -> str:
        return f"VariableReference({self._test_case}, {self._variable_type})"

    def __str__(self) -> str:
        return f"{self._variable_type}"

    def __eq__(self, other: Any) -> bool:
        if self is other:
            return True
        if not isinstance(other, VariableReference):
            return False
        return (
            self._variable_type == other._variable_type
            and self.get_statement_position() == other.get_statement_position()
        )

    def __hash__(self) -> int:
        return 31 * 17 + hash(self._variable_type)
