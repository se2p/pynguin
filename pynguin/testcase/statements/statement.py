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
import logging
from abc import ABCMeta, abstractmethod
from typing import Type, Any

from pynguin.testcase.variable.variablereference import VariableReference


class Statement(metaclass=ABCMeta):
    """An abstract base class of a statement representation."""

    def __init__(self, return_value: VariableReference, return_type: Type,) -> None:
        self._return_value = return_value
        self._return_type = return_type
        self._logger = logging.getLogger(__name__)

    @property
    def return_value(self) -> VariableReference:
        """Provides the return value of this statement.

        :return: The return value of the statement execution
        """
        return self._return_value

    @return_value.setter
    def return_value(self, reference: VariableReference) -> None:
        """Updates the return value of this statement.

        :param reference: The new return value
        """
        self._return_value = reference

    @abstractmethod
    def clone(self) -> "Statement":
        """Provides a deep clone of this statement.

        :return: A deep clone of this statement
        """

    def __eq__(self, other: Any) -> bool:
        pass

    def __hash__(self) -> int:
        pass
