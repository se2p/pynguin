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
"""Provides a stopping condition respecting the global time."""
import logging
import time

import pynguin.configuration as config
from pynguin.generation.stoppingconditions.stoppingcondition import StoppingCondition


class GlobalTimeStoppingCondition(StoppingCondition):
    """Provides a stopping condition respecting the global time."""

    _logger = logging.getLogger(__name__)

    def __init__(self):
        self._start_time = 0

    @property
    def current_value(self) -> int:
        current_time = time.time_ns()
        return (current_time - self._start_time) // 1_000_000_000

    @current_value.setter
    def current_value(self, value: int) -> None:
        self._start_time = value

    def limit(self) -> int:
        return config.INSTANCE.global_timeout

    def is_fulfilled(self) -> bool:
        current_time = time.time_ns()
        if (
            config.INSTANCE.global_timeout != 0
            and self._start_time != 0
            and (current_time - self._start_time) / 1_000_000_000
            > config.INSTANCE.global_timeout
        ):
            self._logger.info("Timeout reached")
            return True
        return False

    def reset(self) -> None:
        if self._start_time == 0:
            self._start_time = time.time_ns()

    def set_limit(self, limit: int) -> None:
        pass

    def iterate(self) -> None:
        pass
