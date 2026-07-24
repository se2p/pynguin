#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Pure metric functions for fitness and coverage."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from pynguin.instrumentation.tracer import ExecutionTrace

if TYPE_CHECKING:
    from pynguin.instrumentation.tracer import SubjectProperties
    from pynguin.testcase.execution import ExecutionResult


def normalise(value: float) -> float:
    """Normalise a value.

    Args:
        value: The value to normalise

    Returns:
        The normalised value

    Raises:
        RuntimeError: if the value is negative
    """
    if value < 0:
        raise RuntimeError("Values to normalise cannot be negative")
    if math.isinf(value):
        return 1.0
    return value / (1.0 + value)


def analyze_results(results: list[ExecutionResult]) -> ExecutionTrace:
    """Merge the trace of the given results.

    Args:
        results: The list of execution results to analyze

    Returns:
        the merged traces.
    """
    merged = ExecutionTrace()
    for result in results:
        trace = result.execution_trace
        assert trace is not None
        merged.merge(trace)
    return merged


def compute_branch_distance_fitness(
    trace: ExecutionTrace,
    subject_properties: SubjectProperties,
    exclude_code: set[int] | None = None,
    exclude_true: set[int] | None = None,
    exclude_false: set[int] | None = None,
) -> float:
    """Computes fitness based on covered branches and branch distances.

    Args:
        trace: The execution trace
        subject_properties: All known data
        exclude_code: Ids of the code objects that should not be considered.
        exclude_true: Ids of predicates whose True branch should not be considered.
        exclude_false: Ids of predicates whose False branch should not be considered.

    Returns:
        The computed fitness value
    """
    # Handle None. Cannot use empty set as default, because of mutable default args.
    exclude_code = set() if exclude_code is None else exclude_code

    # Check if all branch-less code objects were executed.
    code_objects_missing: float = sum(
        1.0
        for code_object_id in subject_properties.branch_less_code_objects
        if code_object_id not in trace.executed_code_objects and code_object_id not in exclude_code
    )
    assert code_objects_missing >= 0.0, "Amount of non covered code objects cannot be negative"

    # Handle None for branches.
    exclude_true = set() if exclude_true is None else exclude_true
    exclude_false = set() if exclude_false is None else exclude_false

    # Check if all predicates are covered
    predicate_fitness: float = 0.0
    for predicate in subject_properties.existing_predicates:
        if predicate not in exclude_true:
            predicate_fitness += _predicate_fitness(predicate, trace.true_distances, trace)
        if predicate not in exclude_false:
            predicate_fitness += _predicate_fitness(predicate, trace.false_distances, trace)

    assert predicate_fitness >= 0.0, "Predicate fitness cannot be negative."
    return code_objects_missing + predicate_fitness


def _predicate_fitness(
    predicate: int, branch_distances: dict[int, float], trace: ExecutionTrace
) -> float:
    if predicate in branch_distances and branch_distances[predicate] == 0.0:
        return 0.0
    if predicate in trace.executed_predicates and trace.executed_predicates[predicate] >= 2:
        return normalise(branch_distances[predicate])
    return 1.0


def compute_branch_distance_fitness_is_covered(
    trace: ExecutionTrace,
    subject_properties: SubjectProperties,
    exclude_code: set[int] | None = None,
    exclude_true: set[int] | None = None,
    exclude_false: set[int] | None = None,
) -> bool:
    """Computes if all branches and code objects have been executed.

    Args:
        trace: The execution trace
        subject_properties: All known data
        exclude_code: Ids of the code objects that should not be considered.
        exclude_true: Ids of predicates whose True branch should not be considered.
        exclude_false: Ids of predicates whose False branch should not be considered.

    Returns:
        True, if all branches were covered
    """
    # Handle None. Cannot use empty set as default, because of mutable default args.
    exclude_code = set() if exclude_code is None else exclude_code

    # Check if all branch-less code objects were executed.
    if any(
        code_object_id not in trace.executed_code_objects and code_object_id not in exclude_code
        for code_object_id in subject_properties.branch_less_code_objects
    ):
        return False

    # Handle None for branches.
    exclude_true = set() if exclude_true is None else exclude_true
    exclude_false = set() if exclude_false is None else exclude_false

    # Check if all predicates are covered
    for predicate in subject_properties.existing_predicates:
        if predicate not in exclude_true and (predicate, 0.0) not in trace.true_distances:
            return False
        if predicate not in exclude_false and (predicate, 0.0) not in trace.false_distances:
            return False
    return True


def compute_line_coverage_fitness_is_covered(
    trace: ExecutionTrace, subject_properties: SubjectProperties
) -> bool:
    """Computes if all lines and code objects have been executed.

    Args:
        trace: The execution trace
        subject_properties: All known data

    Returns:
        True, if all lines were covered, false otherwise
    """
    return len(trace.covered_line_ids) == len(subject_properties.existing_lines)


def compute_checked_coverage_statement_fitness_is_covered(
    trace: ExecutionTrace, subject_properties: SubjectProperties
) -> bool:
    """Computes if all lines and code objects are checked by a return statement.

    Args:
        trace: The execution trace
        subject_properties: All known data

    Returns:
        True, if all lines were checked by a return, false otherwise
    """
    return len(trace.checked_lines) == len(subject_properties.existing_lines)


def compute_branch_coverage(trace: ExecutionTrace, subject_properties: SubjectProperties) -> float:
    """Computes branch coverage on bytecode instructions.

    The resulting coverage should be equal to decision coverage on source code.

    Args:
        trace: The execution trace
        subject_properties: All known data

    Returns:
        The computed coverage value
    """
    covered = len(
        trace.executed_code_objects.intersection(subject_properties.branch_less_code_objects)
    )
    existing = sum(1 for _ in subject_properties.branch_less_code_objects)

    # Every predicate creates two branches
    existing += len(subject_properties.existing_predicates) * 2

    # A branch is covered if it has a distance of 0.0
    # Must consider both branches created by a predicate, i.e. true and false.
    covered += len([v for v in trace.true_distances.values() if v == 0.0])
    covered += len([v for v in trace.false_distances.values() if v == 0.0])

    coverage = 1.0 if existing == 0 else covered / existing
    assert 0.0 <= coverage <= 1.0, "Coverage must be in [0,1]"
    return coverage


def compute_line_coverage(trace: ExecutionTrace, subject_properties: SubjectProperties) -> float:
    """Computes line coverage on bytecode instructions.

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
        covered = len(trace.covered_line_ids)
        coverage = covered / existing
    assert 0.0 <= coverage <= 1.0, "Coverage must be in [0,1]"
    return coverage
