#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides utility functions for fitness calculations."""
from __future__ import annotations

import math
from typing import TYPE_CHECKING, Dict, List, Optional, Set

from pynguin.testcase.execution.executiontrace import ExecutionTrace

if TYPE_CHECKING:
    from pynguin.testcase.execution.executionresult import ExecutionResult
    from pynguin.testcase.execution.executiontracer import KnownData


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


def analyze_results(results: List[ExecutionResult]) -> ExecutionTrace:
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
    known_data: KnownData,
    exclude_code: Optional[Set[int]] = None,
    exclude_true: Optional[Set[int]] = None,
    exclude_false: Optional[Set[int]] = None,
) -> float:
    """Computes fitness based on covered branches and branch distances.

    Args:
        trace: The execution trace
        known_data: All known data
        exclude_code: Ids of the code objects that should not be considered.
        exclude_true: Ids of predicates whose True branch should not be considered.
        exclude_false: Ids of predicates whose False branch should not be considered.

    Returns:
        The computed fitness value
    """
    # Handle None. Cannot use empty set as default, because of mutable default args.
    exclude_code = set() if exclude_code is None else exclude_code

    # Check if all branch-less code objects were executed.
    code_objects_missing: float = len(
        known_data.branch_less_code_objects.difference(
            trace.executed_code_objects, exclude_code
        )
    )
    assert (
        code_objects_missing >= 0.0
    ), "Amount of non covered code objects cannot be negative"

    # Handle None for branches.
    exclude_true = set() if exclude_true is None else exclude_true
    exclude_false = set() if exclude_false is None else exclude_false

    # Check if all predicates are covered
    predicate_fitness: float = 0.0
    for predicate in known_data.existing_predicates:
        if predicate not in exclude_true:
            predicate_fitness += _predicate_fitness(
                predicate, trace.true_distances, trace
            )
        if predicate not in exclude_false:
            predicate_fitness += _predicate_fitness(
                predicate, trace.false_distances, trace
            )
    assert predicate_fitness >= 0.0, "Predicate fitness cannot be negative."
    total_fitness = code_objects_missing + predicate_fitness
    return total_fitness


def _predicate_fitness(
    predicate: int, branch_distances: Dict[int, float], trace: ExecutionTrace
) -> float:
    if predicate in branch_distances and branch_distances[predicate] == 0.0:
        return 0.0
    if (
        predicate in trace.executed_predicates
        and trace.executed_predicates[predicate] >= 2
    ):
        return normalise(branch_distances[predicate])
    return 1.0


def compute_branch_coverage(trace: ExecutionTrace, known_data: KnownData) -> float:
    """Computes branch coverage on bytecode instructions which should equal
    decision coverage on source.

    Args:
        trace: The execution trace
        known_data: All known data

    Returns:
        The computed coverage value
    """

    covered = len(
        trace.executed_code_objects.intersection(known_data.branch_less_code_objects)
    )
    existing = len(known_data.branch_less_code_objects)

    # Every predicate creates two branches
    existing += len(known_data.existing_predicates) * 2

    # A branch is covered if it has a distance of 0.0
    # Must consider both branches created by a predicate, i.e. true and false.
    covered += len([v for v in trace.true_distances.values() if v == 0.0])
    covered += len([v for v in trace.false_distances.values() if v == 0.0])

    if existing == 0:
        # Nothing to cover => everything is covered.
        coverage = 1.0
    else:
        coverage = covered / existing
    assert 0.0 <= coverage <= 1.0, "Coverage must be in [0,1]"
    return coverage


def compare(fitness_1: float, fitness_2: float) -> int:
    """Compare the two specified values.

    Args:
        fitness_1: The first value to compare
        fitness_2: The second value to compare

    Returns:
        the value 0 if fitness_1 is equal to fitness_2; a value less than 0 if
        fitness_1 is less than fitness_2; and a value greater than 0 if fitness_1 is
        greater than fitness_2
    """
    if fitness_1 < fitness_2:
        return -1
    if fitness_1 > fitness_2:
        return 1
    return 0
