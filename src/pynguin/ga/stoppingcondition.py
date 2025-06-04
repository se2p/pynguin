#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT

#  This file is part of Pynguin.
#
#
#  SPDX-License-Identifier: MIT
#
"""Provides an interface for a stopping condition of the algorithm."""

from __future__ import annotations

import logging
import threading
import time

from abc import ABC
from abc import abstractmethod
from typing import TYPE_CHECKING
from typing import Any

import psutil

import pynguin.ga.searchobserver as so

from pynguin.testcase.execution import ExecutionContext
from pynguin.testcase.execution import ExecutionObserver
from pynguin.testcase.execution import ExecutionResult
from pynguin.testcase.execution import RemoteExecutionObserver


if TYPE_CHECKING:
    import ast

    import pynguin.ga.testsuitechromosome as tsc
    import pynguin.testcase.testcase as tc

    from pynguin.testcase.execution import ExecutionContext
    from pynguin.testcase.execution import ExecutionResult
    from pynguin.testcase.execution import TestCaseExecutor
    from pynguin.testcase.statement import Statement
    from pynguin.testcase.testcase import TestCase

_LOGGER = logging.getLogger(__name__)


class RemoteStoppingConditionObserver(RemoteExecutionObserver):
    """A stopping condition observer that can be used remotely."""

    def before_test_case_execution(self, test_case: tc.TestCase):
        """Not used.

        Args:
            test_case: Not used
        """

    def after_test_case_execution(
        self,
        executor: TestCaseExecutor,
        test_case: tc.TestCase,
        result: ExecutionResult,
    ):
        """Not used.

        Args:
            executor: Not used
            test_case: Not used
            result: Not used
        """

    def before_statement_execution(  # noqa: D102
        self, statement: Statement, node: ast.stmt, exec_ctx: ExecutionContext
    ) -> ast.stmt:
        return node

    def after_statement_execution(
        self,
        statement: Statement,
        executor: TestCaseExecutor,
        exec_ctx: ExecutionContext,
        exception: BaseException | None,
    ) -> None:
        """Not used.

        Args:
            statement: Not used
            executor: Not used
            exec_ctx: Not used
            exception: Not used
        """


EMPTY_REMOTE_STOPPING_OBSERVER = RemoteStoppingConditionObserver()


class StoppingCondition(so.SearchObserver, ExecutionObserver, ABC):
    """Provides an interface for a stopping condition of an algorithm."""

    def __init__(self, *, observes_execution: bool = False):  # noqa: D107
        self._observes_execution = observes_execution

    @property
    def remote_observer(self) -> RemoteExecutionObserver:  # noqa: D102
        return EMPTY_REMOTE_STOPPING_OBSERVER

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
        """Returns whether the condition is fulfilled, thus the algorithm should stop.

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
        """Should this observer be attached to the executor?

        Returns:
            Whether this observer should be attached to the executor
        """
        return self._observes_execution

    def before_remote_test_case_execution(self, test_case: TestCase) -> None:
        """Not used.

        Args:
            test_case: Not used
        """

    def after_remote_test_case_execution(self, test_case: tc.TestCase, result: ExecutionResult):
        """Not used.

        Args:
            test_case: Not used
            result: Not used
        """

    def before_search_start(self, start_time_ns: int) -> None:
        """Not used.

        Args:
            start_time_ns: Not used.
        """

    def before_first_search_iteration(self, initial: tsc.TestSuiteChromosome) -> None:
        """Not used.

        Args:
            initial: Not used.
        """

    def after_search_iteration(self, best: tsc.TestSuiteChromosome) -> None:
        """Not used.

        Args:
            best: Not used
        """

    def after_search_finish(self) -> None:
        """Not used."""


class MaxCoverageStoppingCondition(StoppingCondition):
    """A stopping condition that checks for the maximum coverage of the test suite."""

    def __init__(self, max_coverage: int) -> None:
        """Creates a new MaxCoverageStoppingCondition.

        Args:
            max_coverage: the maximum coverage to fulfil the condition
        """
        super().__init__()
        assert 0 <= max_coverage <= 100
        self.__max_coverage = max_coverage
        self.__current_coverage: int = 0

    def current_value(self) -> int:  # noqa: D102
        return self.__current_coverage

    def limit(self) -> int:  # noqa: D102
        return self.__max_coverage

    def is_fulfilled(self) -> bool:  # noqa: D102
        return self.__current_coverage >= self.__max_coverage

    def reset(self) -> None:  # noqa: D102
        self.__current_coverage = 0

    def set_limit(self, limit: int) -> None:  # noqa: D102
        self.__max_coverage = limit

    def before_search_start(self, start_time_ns: int) -> None:  # noqa: D102
        self.__current_coverage = 0

    def after_search_iteration(  # noqa: D102
        self, best: tsc.TestSuiteChromosome
    ) -> None:
        self.__current_coverage = int(best.get_coverage() * 100)

    def __str__(self) -> str:
        return f"Achieved coverage: {self.__current_coverage / self.__max_coverage:.6f}%"


class CoveragePlateauStoppingCondition(StoppingCondition):
    """Fulfilled if coverage does not change for a given number of iterations."""

    def __init__(self, iterations: int) -> None:
        """Creates a new CoveragePlateauStoppingCondition.

        Args:
            iterations: the number of iterations assumed for a plateau
        """
        super().__init__()
        assert iterations > 0
        self.__previous_coverage = 0.0
        self.__unchanged_iterations = 0
        self.__iterations = iterations

    def current_value(self) -> int:  # noqa: D102
        return self.__unchanged_iterations

    def limit(self) -> int:  # noqa: D102
        return self.__iterations

    def is_fulfilled(self) -> bool:  # noqa: D102
        return self.__unchanged_iterations >= self.__iterations

    def reset(self) -> None:  # noqa: D102
        self.__unchanged_iterations = 0
        self.__previous_coverage = 0.0

    def set_limit(self, limit: int) -> None:  # noqa: D102
        self.__iterations = limit

    def before_search_start(self, start_time_ns: int) -> None:  # noqa: D102
        self.reset()

    def after_search_iteration(  # noqa: D102
        self, best: tsc.TestSuiteChromosome
    ) -> None:
        coverage = best.get_coverage()
        if coverage > self.__previous_coverage:
            self.__unchanged_iterations = 0
            self.__previous_coverage = coverage
        elif coverage == self.__previous_coverage:
            self.__unchanged_iterations += 1

    def __str__(self):
        return (
            f"Coverage did not change for {self.__unchanged_iterations} at "
            f"{self.__previous_coverage:.6f}, maximum {self.__iterations}"
        )


class MinimumCoveragePlateauStoppingCondition(StoppingCondition):
    """Signals stop if minimum coverage does not change after iterations."""

    def __init__(self, minimum_coverage: int, plateau_iterations: int) -> None:
        """Instantiates a new stopping condition.

        The condition signals hold if a minimum coverage value was reached but the
        coverage did not change for a given number of algorithm iterations.


        Args:
            minimum_coverage: the minimum coverage values
            plateau_iterations: the number of iterations
        """
        super().__init__()
        assert 0 < minimum_coverage < 100
        assert plateau_iterations > 0
        self.__minimum_coverage = minimum_coverage
        self.__plateau_iterations = plateau_iterations
        self.__last_coverage = 0
        self.__iterations = 0

    def current_value(self) -> int:  # noqa: D102
        return self.__last_coverage

    def limit(self) -> int:  # noqa: D102
        return self.__minimum_coverage

    def is_fulfilled(self) -> bool:  # noqa: D102
        return (
            self.__iterations >= self.__plateau_iterations
            and self.__last_coverage >= self.__minimum_coverage
        )

    def reset(self) -> None:  # noqa: D102
        self.__last_coverage = 0
        self.__iterations = 0

    def set_limit(self, limit: int) -> None:  # noqa: D102
        self.__minimum_coverage = limit

    def before_search_start(self, start_time_ns: int) -> None:  # noqa: D102
        self.reset()

    def after_search_iteration(  # noqa: D102
        self, best: tsc.TestSuiteChromosome
    ) -> None:
        coverage = int(best.get_coverage() * 100)
        if self.__last_coverage == coverage:
            self.__iterations += 1
        else:
            self.__last_coverage = coverage
            self.__iterations = 0

    def __str__(self):
        return (
            f"Coverage did not change for {self.__iterations} iterations while already "
            f"exceeding minimum of {self.__minimum_coverage}%."
        )


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

    def current_value(self) -> int:  # noqa: D102
        return self._num_iterations

    def limit(self) -> int:  # noqa: D102
        return self._max_iterations

    def is_fulfilled(self) -> bool:  # noqa: D102
        return self._num_iterations >= self._max_iterations

    def reset(self) -> None:  # noqa: D102
        self._num_iterations = 0

    def set_limit(self, limit: int) -> None:  # noqa: D102
        self._max_iterations = limit

    def before_search_start(self, start_time_ns: int) -> None:  # noqa: D102
        self._num_iterations = 0

    def after_search_iteration(  # noqa: D102
        self, best: tsc.TestSuiteChromosome
    ) -> None:
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

    def current_value(self) -> int:  # noqa: D102
        return self._num_executed_tests

    def limit(self) -> int:  # noqa: D102
        return self._max_test_executions

    def is_fulfilled(self) -> bool:  # noqa: D102
        return self._num_executed_tests >= self._max_test_executions

    def reset(self) -> None:  # noqa: D102
        self._num_executed_tests = 0

    def set_limit(self, limit: int) -> None:  # noqa: D102
        self._max_test_executions = limit

    def before_search_start(self, start_time_ns: int) -> None:  # noqa: D102
        self._num_executed_tests = 0

    def before_remote_test_case_execution(self, test_case: tc.TestCase):  # noqa: D102
        self._num_executed_tests += 1

    def __str__(self):
        return f"Executed test cases: {self.current_value()}/{self.limit()}"


class RemoteMaxStatementExecutionsObserver(RemoteStoppingConditionObserver):
    """A stopping condition observer that checks the maximum number of executed statements."""

    class RemoteMaxStatementExecutionsObserverState(threading.local):
        """Local state for the remote observer."""

        def __init__(self):  # noqa: D107
            super().__init__()
            self._num_executed_statements = 0

    def __init__(self):
        """Create new RemoteMaxStatementExecutionsObserver."""
        super().__init__()
        self._state = (
            RemoteMaxStatementExecutionsObserver.RemoteMaxStatementExecutionsObserverState()
        )

    @property
    def state(self) -> dict[str, Any]:  # noqa: D102
        return {
            "num_executed_statements": self._state._num_executed_statements  # noqa: SLF001
        }

    @state.setter
    def state(self, state: dict[str, Any]) -> None:
        self._state._num_executed_statements = state[  # noqa: SLF001
            "num_executed_statements"
        ]

    def before_statement_execution(  # noqa: D102
        self,
        statement: Statement,
        node: ast.stmt,
        exec_ctx: ExecutionContext,
    ) -> ast.stmt:
        self._state._num_executed_statements += 1  # noqa: SLF001
        return node

    def after_test_case_execution(  # noqa: D102
        self,
        executor: TestCaseExecutor,
        test_case: TestCase,
        result: ExecutionResult,
    ):
        result.num_executed_statements = (
            self._state._num_executed_statements  # noqa: SLF001
        )


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
        self._remote_observer = RemoteMaxStatementExecutionsObserver()

    @property
    def remote_observer(self) -> RemoteExecutionObserver:  # noqa: D102
        return self._remote_observer

    def current_value(self) -> int:  # noqa: D102
        return self._num_executed_statements

    def limit(self) -> int:  # noqa: D102
        return self._max_executed_statements

    def is_fulfilled(self) -> bool:  # noqa: D102
        return self._num_executed_statements >= self._max_executed_statements

    def reset(self) -> None:  # noqa: D102
        self._num_executed_statements = 0

    def set_limit(self, limit: int) -> None:  # noqa: D102
        self._max_executed_statements = limit

    def before_search_start(self, start_time_ns: int) -> None:  # noqa: D102
        self._num_executed_statements = 0

    def after_remote_test_case_execution(  # noqa: D102
        self, test_case: TestCase, result: ExecutionResult
    ):
        self._num_executed_statements += result.num_executed_statements

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

    def current_value(self) -> int:  # noqa: D102
        return (time.time_ns() - self._start_time) // 1_000_000_000

    def limit(self) -> int:  # noqa: D102
        return self._max_seconds

    def is_fulfilled(self) -> bool:  # noqa: D102
        return ((time.time_ns() - self._start_time) / 1_000_000_000) > self._max_seconds

    def reset(self) -> None:  # noqa: D102
        self._start_time = time.time_ns()

    def set_limit(self, limit: int) -> None:  # noqa: D102
        self._max_seconds = limit

    def before_search_start(self, start_time_ns: int) -> None:  # noqa: D102
        self._start_time = start_time_ns

    def __str__(self):
        return f"Used search time: {self.current_value()}/{self.limit()}"


class MaxMemoryStoppingCondition(StoppingCondition):
    """Stop the search once the memory limit is exceeded.

    The search is only stopped if the memory limit is exceeded after an iteration. In
    case the memory limit is exceeded during an iteration and the memory is limited
    by the environment (e.g. by the operating system/slurm/docker) Pynguin will crash as
    the environment will kill the process. Thus, it is recommended to set the memory
    limit for this stopping condition lower than the actual memory limit of the
    environment.

    Pynguin itself requires less than 1GB of memory in almost all cases. However, the
    tests generated for the SUT can do memory allocations of underlying libraries
    (e.g. numpy, pandas, etc.) which might not get cleaned up properly after the test
    execution due to bugs in the SUT library.
    As Pynguin executes the tests multiple times, this leads to an increasing memory usage
    over time (and could lead to a memory leak). In case the environment kills the process
    no results are available, but if this stopping condition is used (and triggered
    before) Pynguin can finish as usual.

    We could also track the memory usage of the last iteration(s) and estimate the memory
    usage of the next iteration(s), but for now we keep it simple and similar to the
    other stopping conditions.
    """

    MB_TO_BYTES = 1024 * 1024

    def __init__(self, memory_limit_mb: int):
        """Create new MemoryExceededStoppingCondition.

        Args:
            memory_limit_mb: the memory limit in MB
        """
        super().__init__()
        self._memory_limit_bytes = memory_limit_mb * self.MB_TO_BYTES
        self._memory_usage = 0

    def current_value(self) -> int:  # noqa: D102
        return self._memory_usage

    def limit(self) -> int:  # noqa: D102
        return self._memory_limit_bytes

    def is_fulfilled(self) -> bool:  # noqa: D102
        return self._memory_usage > self._memory_limit_bytes

    def reset(self) -> None:  # noqa: D102
        self._memory_usage = 0

    def set_limit(self, limit_mb: int) -> None:
        """Set the memory limit in MB.

        Args:
            limit_mb: the memory limit in MB
        """
        self._memory_limit_bytes = limit_mb * self.MB_TO_BYTES

    def before_search_start(self, start_time_ns: int) -> None:  # noqa: D102
        self._memory_usage = 0

    def after_search_iteration(self, best: tsc.TestSuiteChromosome) -> None:
        """Check the memory usage after each iteration and stop if exceeded.

        Args:
            best: The best test suite chromosome. Unused.
        """
        try:
            self._memory_usage = self._get_memory_usage()
        except Exception:  # noqa: BLE001
            _LOGGER.warning(
                "Failed to get memory usage, assuming 0 bytes used. ",
                exc_info=True,
            )
            self._memory_usage = 0

    @staticmethod
    def _get_memory_usage() -> int:
        """Get the memory usage of the current process in bytes.

        Returns:
            The memory usage in bytes.
        """
        process = psutil.Process()
        return process.memory_info().rss  # Resident Set Size (physical memory)

    def __str__(self):
        return (
            f"Used memory: {self.current_value() / self.MB_TO_BYTES}/"
            f"{self.limit() / self.MB_TO_BYTES} MB"
        )
