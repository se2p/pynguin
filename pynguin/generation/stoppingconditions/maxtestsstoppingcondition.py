#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""A stopping condition that checks the maximum number of test cases."""
import pynguin.configuration as config
from pynguin.generation.stoppingconditions.stoppingcondition import StoppingCondition


class MaxTestsStoppingCondition(StoppingCondition):
    """A stopping condition that checks the maximum number of test cases."""

    def __init__(self):
        self._num_tests = 0
        self._max_tests = config.INSTANCE.search_budget

    def limit(self) -> int:
        return self._max_tests

    def is_fulfilled(self) -> bool:
        return self._num_tests >= self._max_tests

    def reset(self) -> None:
        self._num_tests = 0

    def set_limit(self, limit: int) -> None:
        self._max_tests = limit

    def iterate(self) -> None:
        self._num_tests += 1
