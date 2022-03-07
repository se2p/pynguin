#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides an interface for a stopping condition of the algorithm."""
from __future__ import annotations

import time
from abc import ABCMeta, abstractmethod
from typing import TYPE_CHECKING

import pynguin.generation.searchobserver as so
from pynguin.testcase.execution import ExecutionObserver

if TYPE_CHECKING:
    import pynguin.ga.testsuitechromosome as tsc
    import pynguin.testcase.statement as stmt
    import pynguin.testcase.testcase as tc
    from pynguin.testcase.execution import ExecutionContext, ExecutionResult


class StoppingCondition(so.SearchObserver, ExecutionObserver, metaclass=ABCMeta):
    """Provides an interface for a stopping condition of an algorithm."""

    def __init__(self, observes_execution: bool = False):
        self._observes_execution = observes_execution

    @abstractmethod
    def current_value(self) -> int:
        """Provide how much of the budget we have used.

        Returns:
            The current value of the budget
        """

    @abstractmethod
    def limit(self) -> int:
        """Get upper limit of resources.

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
    def __str__(self):
        pass

    @property
    def observes_execution(self) -> bool:
        """Should this observer be attached to the executor?"""
        return self._observes_execution

    def before_test_case_execution(self, test_case: tc.TestCase):
        pass

    def after_test_case_execution(
        self, test_case: tc.TestCase, result: ExecutionResult
    ):
        pass

    def before_statement_execution(
        self, statement: stmt.Statement, exec_ctx: ExecutionContext
    ):
        pass

    def after_statement_execution(
        self,
        statement: stmt.Statement,
        exec_ctx: ExecutionContext,
        exception: Exception | None = None,
    ) -> None:
        pass

    def before_search_start(self, start_time_ns: int) -> None:
        pass

    def before_first_search_iteration(self, initial: tsc.TestSuiteChromosome) -> None:
        pass

    def after_search_iteration(self, best: tsc.TestSuiteChromosome) -> None:
        pass

    def after_search_finish(self) -> None:
        pass


class MaxIterationsStoppingCondition(StoppingCondition):
    """A stopping condition that checks the maximum number of test cases."""

    def __init__(self, max_iterations: int):
        """Create new MaxIterationsStoppingCondition.

        Args:
            max_iterations: the maximum number of allowed iterations.
        """
        super().__init__()
        self._num_iterations = 0
        assert max_iterations > 0.0
        self._max_iterations = max_iterations

    def current_value(self) -> int:
        return self._num_iterations

    def limit(self) -> int:
        return self._max_iterations

    def is_fulfilled(self) -> bool:
        return self._num_iterations >= self._max_iterations

    def reset(self) -> None:
        self._num_iterations = 0

    def set_limit(self, limit: int) -> None:
        self._max_iterations = limit

    def before_search_start(self, start_time_ns: int) -> None:
        self._num_iterations = 0

    def after_search_iteration(self, best: tsc.TestSuiteChromosome) -> None:
        self._num_iterations += 1

    def __str__(self):
        return f"Used iterations: {self.current_value()}/{self.limit()}"


class MaxTestExecutionsStoppingCondition(StoppingCondition):
    """A stopping condition that checks the maximum number of test case executions."""

    def __init__(self, max_test_executions: int):
        """Create new MaxTestExecutionsStoppingCondition.

        Args:
            max_test_executions: the maximum number of allowed test executions.
        """
        super().__init__(observes_execution=True)
        self._num_executed_tests = 0
        assert max_test_executions > 0.0
        self._max_test_executions = max_test_executions

    def current_value(self) -> int:
        return self._num_executed_tests

    def limit(self) -> int:
        return self._max_test_executions

    def is_fulfilled(self) -> bool:
        return self._num_executed_tests >= self._max_test_executions

    def reset(self) -> None:
        self._num_executed_tests = 0

    def set_limit(self, limit: int) -> None:
        self._max_test_executions = limit

    def before_search_start(self, start_time_ns: int) -> None:
        self._num_executed_tests = 0

    def after_test_case_execution(
        self, test_case: tc.TestCase, result: ExecutionResult
    ):
        self._num_executed_tests += 1

    def __str__(self):
        return f"Executed test cases: {self.current_value()}/{self.limit()}"


class MaxStatementExecutionsStoppingCondition(StoppingCondition):
    """A stopping condition that checks the maximum number of executed statements."""

    def __init__(self, max_executed_statements: int):
        """Create new MaxTestExecutionsStoppingCondition.

        Args:
            max_executed_statements: the maximum number of allowed statement executions.
        """
        super().__init__(observes_execution=True)
        self._num_executed_statements = 0
        assert max_executed_statements > 0.0
        self._max_executed_statements = max_executed_statements

    def current_value(self) -> int:
        return self._num_executed_statements

    def limit(self) -> int:
        return self._max_executed_statements

    def is_fulfilled(self) -> bool:
        return self._num_executed_statements >= self._max_executed_statements

    def reset(self) -> None:
        self._num_executed_statements = 0

    def set_limit(self, limit: int) -> None:
        self._max_executed_statements = limit

    def before_search_start(self, start_time_ns: int) -> None:
        self._num_executed_statements = 0

    def after_statement_execution(
        self,
        statement: stmt.Statement,
        exec_ctx: ExecutionContext,
        exception: Exception | None = None,
    ) -> None:
        self._num_executed_statements += 1

    def __str__(self):
        return f"Executed statements: {self.current_value()}/{self.limit()}"


class MaxSearchTimeStoppingCondition(StoppingCondition):
    """Stop search after a predefined amount of time."""

    def __init__(self, max_seconds: int):
        """Create new MaxTestExecutionsStoppingCondition.

        Args:
            max_seconds: the maximum time (in seconds) that can be used for the search.
        """
        super().__init__()
        self._start_time = 0
        assert max_seconds > 0.0
        self._max_seconds = max_seconds

    def current_value(self) -> int:
        return (time.time_ns() - self._start_time) // 1_000_000_000

    def limit(self) -> int:
        return self._max_seconds

    def is_fulfilled(self) -> bool:
        return ((time.time_ns() - self._start_time) / 1_000_000_000) > self._max_seconds

    def reset(self) -> None:
        self._start_time = time.time_ns()

    def set_limit(self, limit: int) -> None:
        self._max_seconds = limit

    def before_search_start(self, start_time_ns: int) -> None:
        self._start_time = start_time_ns

    def __str__(self):
        return f"Used search time: {self.current_value()}/{self.limit()}"
