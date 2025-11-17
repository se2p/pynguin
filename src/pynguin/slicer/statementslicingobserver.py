#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides an observer that can be used to calculate the checked lines of a test."""

import ast
import threading

import pynguin.testcase.execution as ex
import pynguin.testcase.statement as st
import pynguin.testcase.testcase as tc
from pynguin.ga.computations import compute_statement_checked_lines
from pynguin.slicer.dynamicslicer import SlicingCriterion


class RemoteStatementSlicingObserver(ex.RemoteExecutionObserver):
    """Remote observer that updates the checked lines of a testcase.

    Observes the execution of a test case and calculates the
    slices of its statements.
    """

    _STORE_INSTRUCTION_OFFSET = 2

    class RemoteSlicingLocalState(threading.local):
        """Stores thread-local slicing data."""

        def __init__(self):  # noqa: D107
            super().__init__()
            self.slicing_criteria: dict[int, SlicingCriterion] = {}

    def __init__(self) -> None:
        """Initializes the observer."""
        super().__init__()
        self._slicing_local_state = RemoteStatementSlicingObserver.RemoteSlicingLocalState()

    def before_test_case_execution(self, test_case: tc.TestCase):
        """Not used.

        Args:
            test_case: Not used
        """

    def before_statement_execution(  # noqa: D102
        self, statement: st.Statement, node: ast.stmt, exec_ctx: ex.ExecutionContext
    ) -> ast.stmt:
        return node

    def after_statement_execution(  # noqa: D102
        self,
        statement: st.Statement,
        executor: ex.TestCaseExecutor,
        exec_ctx: ex.ExecutionContext,
        exception: BaseException | None,
    ) -> None:
        if exception is None:
            assert isinstance(statement, st.VariableCreatingStatement)
            trace = executor.subject_properties.instrumentation_tracer.get_trace()
            self._slicing_local_state.slicing_criteria[statement.get_position()] = SlicingCriterion(
                len(trace.executed_instructions) - self._STORE_INSTRUCTION_OFFSET
            )

    def after_test_case_execution(  # noqa: D102
        self,
        executor: ex.TestCaseExecutor,
        test_case: tc.TestCase,
        result: ex.ExecutionResult,
    ) -> None:
        checked_lines = compute_statement_checked_lines(
            test_case.statements,
            result.execution_trace,
            executor.subject_properties,
            self._slicing_local_state.slicing_criteria,
        )
        result.execution_trace.checked_lines.update(checked_lines)
