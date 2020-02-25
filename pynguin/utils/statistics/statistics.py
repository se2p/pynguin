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
"""Provides tracking of statistics for various variables and types."""
from __future__ import annotations
import enum
import queue
from typing import Optional, Any, Generator, Tuple


class RuntimeVariable(enum.Enum):
    """Defines all runtime variables we want to store in the result CSV files.

    A runtime variable is either an output of the generation (e.g., obtained coverage)
    or something that can only be determined once the CUT is analysed (e.g., number of
    branches).

    It is perfectly fine to add new runtime variables in this enum, in any position, but
    it is essential to provide a description for each new variable, because this
    description will become the text in the result.
    """

    total_time = "Total time spent by Pynguin to generate tests"

    def __init__(self, value: str) -> None:
        self._value = value

    @property
    def value(self) -> str:
        return self._value


class StatisticsTracker:
    """A singleton tracker for statistics."""

    _instance: Optional[StatisticsTracker] = None

    def __new__(cls) -> StatisticsTracker:
        if cls._instance is None:
            cls._instance = super(StatisticsTracker, cls).__new__(cls)
            cls._variables: queue.Queue = queue.Queue()
        return cls._instance

    def track_output_variable(self, runtime_variable: RuntimeVariable, value: Any):
        """

        :param runtime_variable:
        :param value:
        :return:
        """
        self._variables.put((runtime_variable, value))

    @property
    def variables(self) -> queue.Queue:
        """Provides the queue of tracked variables"""
        return self._variables

    @property
    def variables_generator(self) -> Generator[Tuple[RuntimeVariable, Any], None, None]:
        """Provides a generator"""
        while not self._variables.empty():
            yield self._variables.get()
