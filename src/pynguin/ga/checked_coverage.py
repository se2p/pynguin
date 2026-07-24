#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Computes checked coverage metrics using slicers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pynguin.instrumentation import version
from pynguin.slicer.dynamicslicer import AssertionSlicer, DynamicSlicer

if TYPE_CHECKING:
    from pynguin.instrumentation.tracer import ExecutionTrace, SubjectProperties
    from pynguin.slicer.dynamicslicer import SlicingCriterion, UniqueInstruction
    from pynguin.testcase.testcase import Statement


def _cleanse_included_implicit_return_none(
    subject_properties: SubjectProperties,
    statement_checked_lines: set[int],
    statement_slice: list[UniqueInstruction],
):
    # check if the last included instructions before the store
    # are a explicit "return None"
    if version.end_with_explicit_return_none(statement_slice[:-1]):
        statement_checked_lines.remove(
            DynamicSlicer.get_line_id_by_instruction(
                statement_slice[-version.RETURN_NONE_SIZE - 1],
                subject_properties,
            )
        )


def compute_statement_checked_lines(
    statements: list[Statement],
    trace: ExecutionTrace,
    subject_properties: SubjectProperties,
    statement_slicing_criteria: dict[int, SlicingCriterion],
) -> set[int]:
    """Computes checked coverage on bytecode instructions.

    Each statement can be sliced, returning a list of instructions
    that are checked by the return value of the statement.
    If we combine all lists of instructions returned by slicing all statements,
    we get the combined dynamic slice of the test execution's statements.
    We then can map all instructions inside the slice to lines
    that are checked covered of the module under test.

    Args:
        statements: The sliced instructions
        trace: The execution trace
        subject_properties: All known data
        statement_slicing_criteria: a dictionary of statement positions
            and its slicing criteria

    Returns:
        The checked line ids of lines checked by the statements
    """
    known_code_objects = subject_properties.existing_code_objects
    dynamic_slicer = DynamicSlicer(known_code_objects)
    checked_lines_ids = set()
    for position, statement in enumerate(statements):
        if statement.bound_variable is None:
            # Unbound Expr statements (e.g. produced by
            # remove_unused_variables()) carry no STORE instruction and thus
            # never get a slicing criterion; skip them without treating this
            # as an execution-aborting gap.
            continue
        if position not in statement_slicing_criteria:
            # if there is no slicing criterion there was an exception during
            # the test case execution and the latter statements after the one
            # with an exception will never be executed,
            # thus having no slicing criterion
            break
        statement_slice = dynamic_slicer.slice(
            trace,
            statement_slicing_criteria[position],
        )
        statement_checked_lines = DynamicSlicer.map_instructions_to_lines(
            statement_slice, subject_properties
        )

        _cleanse_included_implicit_return_none(
            subject_properties,
            statement_checked_lines,
            statement_slice,
        )

        checked_lines_ids.update(statement_checked_lines)
    return checked_lines_ids


def compute_assertion_checked_coverage(
    trace: ExecutionTrace, subject_properties: SubjectProperties
) -> float:
    """Computes checked coverage on bytecode instructions.

    Each assertion can be sliced, returning a list of instructions
    that are checked by an assertion.
    If we combine all lists of instructions returned by slicing all assertions,
    we get the combined dynamic slice of the test execution's assertions.
    We then can map all instructions inside the slice to lines
    that are checked covered of the module under test.
    To calculate the coverage we can then divide the amount of lines checked
    covered through the test execution by the lines overall available in the
    module under test.

    Args:
        trace: The execution trace
        subject_properties: All known data

    Returns:
        The computed coverage value
    """
    existing = len(subject_properties.existing_lines)

    if existing == 0:
        # Nothing to cover => everything is covered.
        coverage = 1.0
    else:
        assertion_slicer = AssertionSlicer(subject_properties.existing_code_objects)
        checked_instructions = []
        for executed_assertion in trace.executed_assertions:
            assertion_checked_instructions = assertion_slicer.slice_assertion(
                executed_assertion, trace
            )
            executed_assertion.assertion.checked_instructions.extend(assertion_checked_instructions)
            # checked at any point by the assertion of a statement
            checked_instructions.extend(assertion_checked_instructions)

        # reduce coverage to lines instead of instructions
        checked_lines = DynamicSlicer.map_instructions_to_lines(
            checked_instructions, subject_properties
        )

        covered = len(checked_lines)
        coverage = covered / existing
    assert 0.0 <= coverage <= 1.0, "Coverage must be in [0,1]"
    return coverage
