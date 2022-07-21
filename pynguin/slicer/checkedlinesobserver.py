#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides an observer that can be used to calculate the checked lines of a test."""
import logging

import pynguin.testcase.execution as ex
import pynguin.testcase.statement as st
import pynguin.testcase.testcase as tc
import pynguin.utils.opcodes as op
from pynguin.ga.computations import compute_statement_checked_lines
from pynguin.slicer.dynamicslicer import SlicingCriterion
from pynguin.slicer.executionflowbuilder import UniqueInstruction
from pynguin.testcase.execution import ExecutionContext

_LOGGER = logging.getLogger(__name__)


class CheckedLineObserver(ex.ExecutionObserver):
    """Observer that updates the checked lines of a testcase.
    Observes the execution of a test case and calculates the
    slices of its statements."""

    def __init__(self, tracer: ex.ExecutionTracer) -> None:
        self._tracer = tracer
        self._slicing_criteria: dict[int, SlicingCriterion] = {}

    def before_test_case_execution(self, test_case: tc.TestCase):
        self._slicing_criteria = {}  # reset known slicing criteria

    def before_statement_execution(
        self, statement: st.Statement, exec_ctx: ExecutionContext
    ):
        # Nothing to do before statement.
        pass

    def after_statement_execution(
        self,
        statement: st.Statement,
        exec_ctx: ex.ExecutionContext,
        exception: Exception | None = None,
    ) -> None:
        if exception is None:
            assert isinstance(statement, st.VariableCreatingStatement)
            trace = self._tracer.get_trace()
            last_traced_instr = trace.executed_instructions[-2]
            assert last_traced_instr.opcode == op.STORE_NAME

            code_object = self._tracer.get_known_data().existing_code_objects[
                last_traced_instr.code_object_id
            ]
            slicing_instruction = UniqueInstruction(
                last_traced_instr.file,
                last_traced_instr.name,
                last_traced_instr.code_object_id,
                last_traced_instr.node_id,
                code_object,
                last_traced_instr.offset,
                arg=last_traced_instr.argument,
                lineno=last_traced_instr.lineno,
            )
            slicing_criterion = SlicingCriterion(
                slicing_instruction,
                len(trace.executed_instructions) - 3,
            )
            self._slicing_criteria[statement.get_position()] = slicing_criterion

    def after_test_case_execution_inside_thread(
        self, test_case: tc.TestCase, result: ex.ExecutionResult
    ):
        checked_lines = compute_statement_checked_lines(
            test_case.statements,
            result.execution_trace,
            self._tracer.get_known_data(),
            self._slicing_criteria,
        )
        result.execution_trace.checked_lines.update(checked_lines)

    def after_test_case_execution_outside_thread(
        self, test_case: tc.TestCase, result: ex.ExecutionResult
    ):
        pass
