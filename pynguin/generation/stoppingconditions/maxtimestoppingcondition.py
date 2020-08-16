#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
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
