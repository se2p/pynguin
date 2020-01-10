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
from abc import ABCMeta, abstractmethod
from typing import Type


class VariableReference(metaclass=ABCMeta):
    """Represents a variable in a test case."""

    def __init__(self, variable_type: Type) -> None:
        self._variable_type = variable_type

    @abstractmethod
    def clone(self) -> "VariableReference":
        """Provides a deep copy of the current variable.

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
