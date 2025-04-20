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
import pynguin.utils.opcodes as op

from pynguin.ga.computations import compute_statement_checked_lines
from pynguin.slicer.dynamicslicer import SlicingCriterion
from pynguin.slicer.executionflowbuilder import UniqueInstruction


class RemoteStatementSlicingObserver(ex.RemoteExecutionObserver):
    """Remote observer that updates the checked lines of a testcase.

    Observes the execution of a test case and calculates the
    slices of its statements.
    """

    _STORE_INSTRUCTION_OFFSET = 3

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
            trace = executor.tracer.get_trace()
            last_traced_instr = trace.executed_instructions[-2]
            assert last_traced_instr.opcode == op.STORE_NAME

            code_object = executor.tracer.get_subject_properties().existing_code_objects[
                last_traced_instr.code_object_id
            ]
            slicing_instruction = UniqueInstruction(
                file=last_traced_instr.file,
                name=last_traced_instr.name,
                code_object_id=last_traced_instr.code_object_id,
                node_id=last_traced_instr.node_id,
                code_meta=code_object,
                offset=last_traced_instr.offset,
                arg=last_traced_instr.argument,
                lineno=last_traced_instr.lineno,
            )
            slicing_criterion = SlicingCriterion(
                slicing_instruction,
                len(trace.executed_instructions) - self._STORE_INSTRUCTION_OFFSET,
            )
            self._slicing_local_state.slicing_criteria[statement.get_position()] = slicing_criterion

    def after_test_case_execution(  # noqa: D102
        self,
        executor: ex.TestCaseExecutor,
        test_case: tc.TestCase,
        result: ex.ExecutionResult,
    ) -> None:
        checked_lines = compute_statement_checked_lines(
            test_case.statements,
            result.execution_trace,
            executor.tracer.get_subject_properties(),
            self._slicing_local_state.slicing_criteria,
        )
        result.execution_trace.checked_lines.update(checked_lines)
