#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""A stopping condition that checks the maximum number of test cases."""
import pynguin.configuration as config
from pynguin.generation.stoppingconditions.stoppingcondition import StoppingCondition


class MaxIterationsStoppingCondition(StoppingCondition):
    """A stopping condition that checks the maximum number of test cases."""

    def __init__(self):
        self._num_iterations = 0
        self._max_iterations = config.INSTANCE.algorithm_iterations

    def limit(self) -> int:
        return self._max_iterations

    def is_fulfilled(self) -> bool:
        return self._num_iterations >= self._max_iterations

    def reset(self) -> None:
        self._num_iterations = 0

    def set_limit(self, limit: int) -> None:
        self._max_iterations = limit

    def iterate(self) -> None:
        self._num_iterations += 1
