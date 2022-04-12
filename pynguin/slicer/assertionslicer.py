#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides logic to get the checked instructions of an assertion in a testcase."""
import pynguin.assertion.assertion as ass
from pynguin.slicer.dynamicslicer import DynamicSlicer, SlicingCriterion
from pynguin.slicer.instruction import UniqueInstruction
from pynguin.testcase.execution import (
    CodeObjectMetaData,
    ExecutionTrace,
    ExecutionTracer,
)


# pylint:disable=too-few-public-methods
class AssertionSlicer:
    """Holds all logic of slicing traced assertions to generate the
    dynamic slice produced by a test."""

    def __init__(self, tracer):
        self._tracer: ExecutionTracer = tracer
        self._known_code_objects: dict[int, CodeObjectMetaData] | None = None

    def _slicing_criterion_from_assertion(
        self, trace: ExecutionTrace, assertion: ass.Assertion
    ) -> tuple[SlicingCriterion, int]:
        # TODO(SiL) can the untraced assertion have a position?
        trace_position = 1  # assertion.trace_position_end
        traced_instr = trace.executed_instructions[trace_position]

        assert self._known_code_objects
        code_meta = self._known_code_objects.get(traced_instr.code_object_id)
        unique_instr = UniqueInstruction(
            traced_instr.file,
            traced_instr.name,
            traced_instr.code_object_id,
            traced_instr.node_id,
            code_meta,
            traced_instr.offset,
            traced_instr.argument,
            traced_instr.lineno,
        )

        # We know the exact trace position and the slicer
        # can handle this without having the occurrence.
        return SlicingCriterion(unique_instr, occurrence=-1), trace_position

    def slice_assertion(self, assertion: ass.Assertion) -> list[UniqueInstruction]:
        """Calculate the dynamic slice for an assertion inside a test case

        Args:
            assertion: The assertion, for which to calculate the slice.

        Returns:
            The list of executed instructions contained in the slice of the assertion.
        """

        trace = self._tracer.get_trace()
        known_code_objects = self._tracer.get_known_data().existing_code_objects

        slicing_criterion, trace_position = self._slicing_criterion_from_assertion(
            trace, assertion
        )
        slicer = DynamicSlicer(trace, known_code_objects)

        return slicer.slice(trace, slicing_criterion, trace_position - 1)
