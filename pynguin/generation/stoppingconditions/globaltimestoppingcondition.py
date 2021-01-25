#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
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
        return config.configuration.global_timeout

    def is_fulfilled(self) -> bool:
        current_time = time.time_ns()
        if (
            config.configuration.global_timeout != 0
            and self._start_time != 0
            and (current_time - self._start_time) / 1_000_000_000
            > config.configuration.global_timeout
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
