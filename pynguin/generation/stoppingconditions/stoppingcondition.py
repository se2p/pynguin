#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides an interface for a stopping condition of the algorithm."""
import logging
import time
from abc import ABCMeta, abstractmethod

import pynguin.configuration as config


class StoppingCondition(metaclass=ABCMeta):
    """Provides an interface for a stopping condition of the algorithm."""

    _current_value = 0

    @property
    def current_value(self) -> int:
        """Provide how much of the budget we have used.

        Returns:
            The current value of the budget
        """
        return self._current_value

    @current_value.setter
    def current_value(self, value: int) -> None:
        """Forces a specific amount of used budget.  Handle with care!

        Args:
            value: The new amount of used budget for this StoppingCondition
        """
        self._current_value = value

    @abstractmethod
    def limit(self) -> int:
        """Get upper limit of resources.

        Mainly used for `__repr__()` and `__str__()`

        Returns:
            The limit  # noqa: DAR202
        """

    @abstractmethod
    def is_fulfilled(self) -> bool:
        """Returns whether the condition is fulfilled, thus the algorithm should stop

        Returns:
            True if the condition is fulfilled, False otherwise  # noqa: DAR202
        """

    @abstractmethod
    def reset(self) -> None:
        """Reset everything."""

    @abstractmethod
    def set_limit(self, limit: int) -> None:
        """Sets new upper limit of resources.

        Args:
            limit: The new upper limit
        """

    @abstractmethod
    def iterate(self) -> None:
        """Shall be called in each algorithm iteration.

        Does nothing if the stopping condition does not care for algorithm
        iterations, it must not raise an exception in such a case!
        """


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


class MaxIterationsStoppingCondition(StoppingCondition):
    """A stopping condition that checks the maximum number of test cases."""

    def __init__(self):
        self._num_iterations = 0
        self._max_iterations = config.configuration.algorithm_iterations

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


class MaxTestsStoppingCondition(StoppingCondition):
    """A stopping condition that checks the maximum number of test cases."""

    def __init__(self):
        self._num_tests = 0
        self._max_tests = config.configuration.maximum_test_number

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


class MaxTimeStoppingCondition(StoppingCondition):
    """Stop search after a predefined amount of time."""

    def __init__(self):
        self._max_seconds = config.configuration.budget
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
