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
"""Provides a stopping condition that stops the search after a predefined amount of
time."""
import time

import pynguin.configuration as config
from pynguin.generation.stoppingconditions.stoppingcondition import StoppingCondition


class MaxTimeStoppingCondition(StoppingCondition):
    """Stop search after a predefined amount of time."""

    def __init__(self):
        self._max_seconds = config.INSTANCE.budget
        self._start_time = 0

    def limit(self) -> int:
        return self._max_seconds

    def is_fulfilled(self) -> bool:
        current_time = time.time_ns()
        return (current_time - self._start_time) / 1_000_000_000 > self._max_seconds

    def reset(self) -> None:
        self._start_time = time.time_ns()

    def set_limit(self, limit: int) -> None:
        self._max_seconds = limit

    def iterate(self) -> None:
        pass
