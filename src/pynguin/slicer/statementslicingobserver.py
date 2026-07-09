#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides an observer that can be used to calculate the checked lines of a test."""

from __future__ import annotations

import threading
from typing import Any

import pynguin.testcase.execution as ex
import pynguin.testcase.testcase as tc
from pynguin.ga.computations import compute_statement_checked_lines
from pynguin.slicer.dynamicslicer import SlicingCriterion


class RemoteStatementSlicingObserver(ex.RemoteExecutionObserver):
    """Remote observer that updates the checked lines of a testcase.

    Records, for every bound statement of a test case, the trace position of
    its ``STORE`` instruction as a slicing criterion, then slices backwards
    from each criterion once the test case has finished executing to compute
    the set of module lines that were "checked" (i.e. that influenced the
    value stored by some statement).
    """

    _STORE_INSTRUCTION_OFFSET = 2

    class RemoteSlicingLocalState(threading.local):
        """Stores thread-local slicing data."""

        def __init__(self):  # noqa: D107
            super().__init__()
            self.slicing_criteria: dict[int, SlicingCriterion] = {}
            # Statements execute in a simple sequential loop (see
            # TestCaseExecutor._execute_test_case) inside a fresh thread per
            # test case, so there is no Statement.get_position() any more;
            # track the position ourselves, incremented once per
            # after_statement_execution call. Mirrors
            # RemoteAssertionTraceObserver.RemoteAssertionLocalState.position.
            self.position: int = 0

    def __init__(self) -> None:
        """Initializes the observer."""
        super().__init__()
        self._slicing_local_state = RemoteStatementSlicingObserver.RemoteSlicingLocalState()

    def before_test_case_execution(self, test_case: tc.TestCase):
        """Not used.

        Args:
            test_case: Not used
        """

    def after_statement_execution(
        self,
        statement: tc.Statement,
        executor: ex.TestCaseExecutor,
        namespace: dict[str, Any],
        exception: BaseException | None,
    ) -> None:
        """Record a slicing criterion for the just-executed statement.

        Only bound statements (``statement.bound_variable is not None``) emit
        a ``STORE`` instruction; unbound ``Expr`` statements (e.g. produced by
        ``remove_unused_variables()``) do not and therefore get no criterion.

        Args:
            statement: The statement that was executed.
            executor: The executor that executed the statement.
            namespace: The shared namespace the statement executed in.
            exception: The exception raised by the statement, if any.
        """
        position = self._slicing_local_state.position
        self._slicing_local_state.position = position + 1

        if exception is None and statement.bound_variable is not None:
            trace = executor.subject_properties.instrumentation_tracer.get_trace()
            self._slicing_local_state.slicing_criteria[position] = SlicingCriterion(
                len(trace.executed_instructions) - self._STORE_INSTRUCTION_OFFSET
            )

    def after_test_case_execution(
        self,
        executor: ex.TestCaseExecutor,
        test_case: tc.TestCase,
        result: ex.ExecutionResult,
    ) -> None:
        """Slice all recorded criteria and record the checked lines.

        Args:
            executor: The executor that executed the test case
            test_case: The test case that was executed
            result: The execution result
        """
        checked_lines = compute_statement_checked_lines(
            test_case.statements(),
            result.execution_trace,
            executor.subject_properties,
            self._slicing_local_state.slicing_criteria,
        )
        result.execution_trace.checked_lines.update(checked_lines)
