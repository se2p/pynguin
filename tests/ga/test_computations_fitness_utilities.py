#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
from unittest.mock import MagicMock, patch

import hypothesis.strategies as st
import pytest
from hypothesis import given

import pynguin.ga.computations as ff
from pynguin.instrumentation.instrumentation import PredicateMetaData
from pynguin.slicer.dynamicslicer import AssertionSlicer
from pynguin.testcase.execution import (
    ExecutionResult,
    ExecutionTrace,
    KnownData,
    LineMetaData,
)


def test_normalise_less_zero():
    with pytest.raises(RuntimeError):
        ff.normalise(-1)


def test_normalise_infinity():
    assert ff.normalise(float("inf")) == 1.0


@given(
    st.floats(
        min_value=0.0, max_value=float("inf"), exclude_min=False, exclude_max=True
    )
)
def test_normalise(value):
    assert ff.normalise(value) == value / (1.0 + value)


@pytest.fixture()
def trace_mock():
    return ExecutionTrace()


@pytest.fixture()
def known_data_mock():
    return KnownData()


def test_default_fitness(trace_mock, known_data_mock):
    assert ff.compute_branch_distance_fitness(trace_mock, known_data_mock) == 0


def test_fitness_function_diff(trace_mock, known_data_mock):
    known_data_mock.branch_less_code_objects = {0, 1, 2}
    trace_mock.executed_code_objects.add(0)
    assert ff.compute_branch_distance_fitness(trace_mock, known_data_mock) == 2.0


def test_fitness_covered(trace_mock, known_data_mock):
    known_data_mock.existing_predicates[0] = MagicMock(PredicateMetaData)
    trace_mock.executed_predicates[0] = 1
    trace_mock.false_distances[0] = 1
    trace_mock.true_distances[0] = 0
    assert ff.compute_branch_distance_fitness(trace_mock, known_data_mock) == 1.0


def test_fitness_neither_covered(trace_mock, known_data_mock):
    known_data_mock.existing_predicates[0] = MagicMock(PredicateMetaData)
    assert ff.compute_branch_distance_fitness(trace_mock, known_data_mock) == 2.0


def test_fitness_covered_twice(trace_mock, known_data_mock):
    known_data_mock.existing_predicates[0] = MagicMock(PredicateMetaData)
    trace_mock.executed_predicates[0] = 2
    trace_mock.false_distances[0] = 1
    trace_mock.true_distances[0] = 0
    assert ff.compute_branch_distance_fitness(trace_mock, known_data_mock) == 0.5


def test_fitness_covered_both(trace_mock, known_data_mock):
    known_data_mock.existing_predicates[0] = MagicMock(PredicateMetaData)
    trace_mock.executed_predicates[0] = 2
    trace_mock.false_distances[0] = 0
    trace_mock.true_distances[0] = 0
    assert ff.compute_branch_distance_fitness(trace_mock, known_data_mock) == 0.0


def test_fitness_normalized(trace_mock, known_data_mock):
    known_data_mock.existing_predicates[0] = MagicMock(PredicateMetaData)
    trace_mock.executed_predicates[0] = 2
    trace_mock.false_distances[0] = 0
    trace_mock.true_distances[0] = 7.0
    assert ff.compute_branch_distance_fitness(trace_mock, known_data_mock) == 0.875


def test_branch_coverage_none(known_data_mock, trace_mock):
    assert ff.compute_branch_coverage(trace_mock, known_data_mock) == 1.0


def test_branch_coverage_half_branch(known_data_mock, trace_mock):
    known_data_mock.existing_predicates[0] = MagicMock(PredicateMetaData)
    trace_mock.true_distances[0] = 0.0
    assert ff.compute_branch_coverage(trace_mock, known_data_mock) == 0.5


def test_branch_coverage_no_branch(known_data_mock, trace_mock):
    known_data_mock.existing_predicates[0] = MagicMock(PredicateMetaData)
    assert ff.compute_branch_coverage(trace_mock, known_data_mock) == 0.0


def test_branch_coverage_half_code_objects(known_data_mock, trace_mock):
    known_data_mock.branch_less_code_objects = {0, 1}
    trace_mock.executed_code_objects.add(0)
    assert ff.compute_branch_coverage(trace_mock, known_data_mock) == 0.5


def test_branch_coverage_no_code_objects(known_data_mock, trace_mock):
    known_data_mock.branch_less_code_objects = {0, 1}
    assert ff.compute_branch_coverage(trace_mock, known_data_mock) == 0.0


def test_line_coverage_none(known_data_mock, trace_mock):
    assert ff.compute_line_coverage(trace_mock, known_data_mock) == 1.0


def test_statement_coverage_zero(known_data_mock, trace_mock):
    known_data_mock.existing_lines = {
        0: LineMetaData(0, "foo", 0),
        1: LineMetaData(0, "foo", 1),
    }
    assert ff.compute_line_coverage(trace_mock, known_data_mock) == 0.0


def test_line_coverage_half_covered(known_data_mock, trace_mock):
    known_data_mock.existing_lines = {
        0: LineMetaData(0, "foo", 0),
        1: LineMetaData(0, "foo", 1),
    }
    trace_mock.covered_line_ids = {0}
    assert ff.compute_line_coverage(trace_mock, known_data_mock) == 0.5


def test_line_coverage_fully_covered(known_data_mock, trace_mock):
    known_data_mock.existing_lines = {
        0: LineMetaData(0, "foo", 0),
        1: LineMetaData(0, "foo", 1),
    }
    trace_mock.covered_line_ids = {0, 1}
    assert ff.compute_line_coverage(trace_mock, known_data_mock) == 1.0


def test_line_coverage_is_not_covered(known_data_mock, trace_mock):
    known_data_mock.existing_lines = {
        0: LineMetaData(0, "foo", 0),
        1: LineMetaData(0, "foo", 1),
    }
    trace_mock.covered_line_ids = {0}
    assert not ff.compute_line_coverage_fitness_is_covered(trace_mock, known_data_mock)


def test_line_coverage_is_covered(known_data_mock, trace_mock):
    known_data_mock.existing_lines = {
        0: LineMetaData(0, "foo", 0),
        1: LineMetaData(0, "foo", 1),
    }
    trace_mock.covered_line_ids = {0, 1}
    assert ff.compute_line_coverage_fitness_is_covered(trace_mock, known_data_mock)


def test_checked_coverage_none(known_data_mock, trace_mock):
    assert ff.compute_checked_coverage(trace_mock, known_data_mock) == 1.0


def test_checked_coverage_zero(known_data_mock, trace_mock):
    known_data_mock.existing_lines = {
        0: LineMetaData(0, "foo", 0),
        1: LineMetaData(0, "foo", 1),
    }
    assert ff.compute_checked_coverage(trace_mock, known_data_mock) == 0.0


def test_checked_coverage_half_covered(known_data_mock, trace_mock):
    known_data_mock.existing_lines = {
        0: LineMetaData(0, "foo", 0),
        1: LineMetaData(0, "foo", 1),
    }
    trace_mock.executed_assertions = [MagicMock()]
    mock_instr_1 = MagicMock()
    mock_instr_1.lineno = 0
    with patch.object(AssertionSlicer, "slice_assertion") as slice_mock:
        slice_mock.return_value = [mock_instr_1]
        assert ff.compute_checked_coverage(trace_mock, known_data_mock) == 0.5


def test_checked_coverage_fully_covered(known_data_mock, trace_mock):
    known_data_mock.existing_lines = {
        0: LineMetaData(0, "foo", 0),
        1: LineMetaData(0, "foo", 1),
    }
    trace_mock.executed_assertions = [MagicMock()]
    mock_instr_1 = MagicMock()
    mock_instr_1.lineno = 0
    mock_instr_2 = MagicMock()
    mock_instr_2.lineno = 1
    with patch.object(AssertionSlicer, "slice_assertion") as slice_mock:
        slice_mock.return_value = [mock_instr_1, mock_instr_2]
        assert ff.compute_checked_coverage(trace_mock, known_data_mock) == 1


def test_analyze_traces_empty():
    results = []
    trace = ff.analyze_results(results)
    assert trace == ExecutionTrace()


def test_analyze_traces_merge(trace_mock):
    results = []
    result = MagicMock(ExecutionResult)
    trace_mock.true_distances[0] = 1
    trace_mock.true_distances[1] = 2
    trace_mock.executed_predicates[0] = 1
    trace_mock.executed_code_objects.add(0)
    trace_mock.covered_line_ids = {0, 1}
    result.execution_trace = trace_mock
    results.append(result)
    trace = ff.analyze_results(results)
    assert trace == trace_mock
