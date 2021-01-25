#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
from unittest.mock import MagicMock

import hypothesis.strategies as st
import pytest
from hypothesis import given

from pynguin.ga.fitnessfunctions.fitness_utilities import (
    analyze_results,
    compute_branch_coverage,
    compute_branch_distance_fitness,
    normalise,
)
from pynguin.testcase.execution.executionresult import ExecutionResult
from pynguin.testcase.execution.executiontrace import ExecutionTrace
from pynguin.testcase.execution.executiontracer import (
    CodeObjectMetaData,
    KnownData,
    PredicateMetaData,
)


def test_normalise_less_zero():
    with pytest.raises(RuntimeError):
        normalise(-1)


def test_normalise_infinity():
    assert normalise(float("inf")) == 1.0


@given(
    st.floats(
        min_value=0.0, max_value=float("inf"), exclude_min=False, exclude_max=True
    )
)
def test_normalise(value):
    assert normalise(value) == value / (1.0 + value)


@pytest.fixture()
def trace_mock():
    return ExecutionTrace()


@pytest.fixture()
def known_data_mock():
    return KnownData()


def test_default_fitness(trace_mock, known_data_mock):
    assert compute_branch_distance_fitness(trace_mock, known_data_mock) == 0


def test_fitness_function_diff(trace_mock, known_data_mock):
    known_data_mock.existing_code_objects[0] = MagicMock(CodeObjectMetaData)
    known_data_mock.existing_code_objects[1] = MagicMock(CodeObjectMetaData)
    known_data_mock.existing_code_objects[2] = MagicMock(CodeObjectMetaData)
    trace_mock.executed_code_objects.add(0)
    assert compute_branch_distance_fitness(trace_mock, known_data_mock) == 2.0


def test_fitness_covered(trace_mock, known_data_mock):
    known_data_mock.existing_predicates[0] = MagicMock(PredicateMetaData)
    trace_mock.executed_predicates[0] = 1
    trace_mock.false_distances[0] = 1
    trace_mock.true_distances[0] = 0
    assert compute_branch_distance_fitness(trace_mock, known_data_mock) == 1.0


def test_fitness_neither_covered(trace_mock, known_data_mock):
    known_data_mock.existing_predicates[0] = MagicMock(PredicateMetaData)
    assert compute_branch_distance_fitness(trace_mock, known_data_mock) == 2.0


def test_fitness_covered_twice(trace_mock, known_data_mock):
    known_data_mock.existing_predicates[0] = MagicMock(PredicateMetaData)
    trace_mock.executed_predicates[0] = 2
    trace_mock.false_distances[0] = 1
    trace_mock.true_distances[0] = 0
    assert compute_branch_distance_fitness(trace_mock, known_data_mock) == 0.5


def test_fitness_covered_both(trace_mock, known_data_mock):
    known_data_mock.existing_predicates[0] = MagicMock(PredicateMetaData)
    trace_mock.executed_predicates[0] = 2
    trace_mock.false_distances[0] = 0
    trace_mock.true_distances[0] = 0
    assert compute_branch_distance_fitness(trace_mock, known_data_mock) == 0.0


def test_fitness_normalized(trace_mock, known_data_mock):
    known_data_mock.existing_predicates[0] = MagicMock(PredicateMetaData)
    trace_mock.executed_predicates[0] = 2
    trace_mock.false_distances[0] = 0
    trace_mock.true_distances[0] = 7.0
    assert compute_branch_distance_fitness(trace_mock, known_data_mock) == 0.875


def test_coverage_none(known_data_mock, trace_mock):
    assert compute_branch_coverage(trace_mock, known_data_mock) == 1.0


def test_coverage_half_branch(known_data_mock, trace_mock):
    known_data_mock.existing_predicates[0] = MagicMock(PredicateMetaData)
    trace_mock.true_distances[0] = 0.0
    assert compute_branch_coverage(trace_mock, known_data_mock) == 0.5


def test_coverage_no_branch(known_data_mock, trace_mock):
    known_data_mock.existing_predicates[0] = MagicMock(PredicateMetaData)
    assert compute_branch_coverage(trace_mock, known_data_mock) == 0.0


def test_coverage_half_code_objects(known_data_mock, trace_mock):
    known_data_mock.existing_code_objects[0] = MagicMock(CodeObjectMetaData)
    known_data_mock.existing_code_objects[1] = MagicMock(CodeObjectMetaData)
    trace_mock.executed_code_objects.add(0)
    assert compute_branch_coverage(trace_mock, known_data_mock) == 0.5


def test_coverage_no_code_objects(known_data_mock, trace_mock):
    known_data_mock.existing_code_objects[0] = MagicMock(CodeObjectMetaData)
    known_data_mock.existing_code_objects[1] = MagicMock(CodeObjectMetaData)
    assert compute_branch_coverage(trace_mock, known_data_mock) == 0.0


def test_analyze_traces_empty():
    results = []
    trace = analyze_results(results)
    assert trace == ExecutionTrace()


def test_analyze_traces_merge(trace_mock):
    results = []
    result = MagicMock(ExecutionResult)
    trace_mock.true_distances[0] = 1
    trace_mock.true_distances[1] = 2
    trace_mock.executed_predicates[0] = 1
    trace_mock.executed_code_objects.add(0)
    result.execution_trace = trace_mock
    results.append(result)
    trace = analyze_results(results)
    assert trace == trace_mock
