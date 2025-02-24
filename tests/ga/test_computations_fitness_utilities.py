#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
from unittest.mock import MagicMock
from unittest.mock import patch

import hypothesis.strategies as st
import pytest

from hypothesis import given

import pynguin.ga.computations as ff

from pynguin.instrumentation.instrumentation import PredicateMetaData
from pynguin.instrumentation.tracer import ExecutedAssertion
from pynguin.instrumentation.tracer import ExecutionTrace
from pynguin.instrumentation.tracer import LineMetaData
from pynguin.instrumentation.tracer import SubjectProperties
from pynguin.slicer.dynamicslicer import AssertionSlicer
from pynguin.slicer.dynamicslicer import DynamicSlicer
from pynguin.testcase.execution import ExecutionResult
from pynguin.utils.orderedset import OrderedSet


def test_normalise_less_zero():
    with pytest.raises(RuntimeError):
        ff.normalise(-1)


def test_normalise_infinity():
    assert ff.normalise(float("inf")) == 1.0


@given(st.floats(min_value=0.0, max_value=float("inf"), exclude_min=False, exclude_max=True))
def test_normalise(value):
    assert ff.normalise(value) == value / (1.0 + value)


@pytest.fixture
def trace_mock():
    return ExecutionTrace()


@pytest.fixture
def subject_properties_mock():
    return SubjectProperties()


def test_default_fitness(trace_mock, subject_properties_mock):
    assert ff.compute_branch_distance_fitness(trace_mock, subject_properties_mock) == 0


def test_fitness_function_diff(trace_mock, subject_properties_mock):
    subject_properties_mock.branch_less_code_objects = {0, 1, 2}
    trace_mock.executed_code_objects.add(0)
    assert ff.compute_branch_distance_fitness(trace_mock, subject_properties_mock) == 2.0


def test_fitness_covered(trace_mock, subject_properties_mock):
    subject_properties_mock.existing_predicates[0] = MagicMock(PredicateMetaData)
    trace_mock.executed_predicates[0] = 1
    trace_mock.false_distances[0] = 1
    trace_mock.true_distances[0] = 0
    assert ff.compute_branch_distance_fitness(trace_mock, subject_properties_mock) == 1.0


def test_fitness_neither_covered(trace_mock, subject_properties_mock):
    subject_properties_mock.existing_predicates[0] = MagicMock(PredicateMetaData)
    assert ff.compute_branch_distance_fitness(trace_mock, subject_properties_mock) == 2.0


def test_fitness_covered_twice(trace_mock, subject_properties_mock):
    subject_properties_mock.existing_predicates[0] = MagicMock(PredicateMetaData)
    trace_mock.executed_predicates[0] = 2
    trace_mock.false_distances[0] = 1
    trace_mock.true_distances[0] = 0
    assert ff.compute_branch_distance_fitness(trace_mock, subject_properties_mock) == 0.5


def test_fitness_covered_both(trace_mock, subject_properties_mock):
    subject_properties_mock.existing_predicates[0] = MagicMock(PredicateMetaData)
    trace_mock.executed_predicates[0] = 2
    trace_mock.false_distances[0] = 0
    trace_mock.true_distances[0] = 0
    assert ff.compute_branch_distance_fitness(trace_mock, subject_properties_mock) == 0.0


def test_fitness_normalized(trace_mock, subject_properties_mock):
    subject_properties_mock.existing_predicates[0] = MagicMock(PredicateMetaData)
    trace_mock.executed_predicates[0] = 2
    trace_mock.false_distances[0] = 0
    trace_mock.true_distances[0] = 7.0
    assert ff.compute_branch_distance_fitness(trace_mock, subject_properties_mock) == 0.875


def test_branch_coverage_none(subject_properties_mock, trace_mock):
    assert ff.compute_branch_coverage(trace_mock, subject_properties_mock) == 1.0


def test_branch_coverage_half_branch(subject_properties_mock, trace_mock):
    subject_properties_mock.existing_predicates[0] = MagicMock(PredicateMetaData)
    trace_mock.true_distances[0] = 0.0
    assert ff.compute_branch_coverage(trace_mock, subject_properties_mock) == 0.5


def test_branch_coverage_no_branch(subject_properties_mock, trace_mock):
    subject_properties_mock.existing_predicates[0] = MagicMock(PredicateMetaData)
    assert ff.compute_branch_coverage(trace_mock, subject_properties_mock) == 0.0


def test_branch_coverage_half_code_objects(subject_properties_mock, trace_mock):
    subject_properties_mock.branch_less_code_objects = {0, 1}
    trace_mock.executed_code_objects.add(0)
    assert ff.compute_branch_coverage(trace_mock, subject_properties_mock) == 0.5


def test_branch_coverage_no_code_objects(subject_properties_mock, trace_mock):
    subject_properties_mock.branch_less_code_objects = {0, 1}
    assert ff.compute_branch_coverage(trace_mock, subject_properties_mock) == 0.0


def test_line_coverage_none(subject_properties_mock, trace_mock):
    assert ff.compute_line_coverage(trace_mock, subject_properties_mock) == 1.0


def test_statement_coverage_zero(subject_properties_mock, trace_mock):
    subject_properties_mock.existing_lines = {
        0: LineMetaData(0, "foo", 0),
        1: LineMetaData(0, "foo", 1),
    }
    assert ff.compute_line_coverage(trace_mock, subject_properties_mock) == 0.0


def test_line_coverage_half_covered(subject_properties_mock, trace_mock):
    subject_properties_mock.existing_lines = {
        0: LineMetaData(0, "foo", 0),
        1: LineMetaData(0, "foo", 1),
    }
    trace_mock.covered_line_ids = {0}
    assert ff.compute_line_coverage(trace_mock, subject_properties_mock) == 0.5


def test_line_coverage_fully_covered(subject_properties_mock, trace_mock):
    subject_properties_mock.existing_lines = {
        0: LineMetaData(0, "foo", 0),
        1: LineMetaData(0, "foo", 1),
    }
    trace_mock.covered_line_ids = {0, 1}
    assert ff.compute_line_coverage(trace_mock, subject_properties_mock) == 1.0


def test_line_coverage_is_not_covered(subject_properties_mock, trace_mock):
    subject_properties_mock.existing_lines = {
        0: LineMetaData(0, "foo", 0),
        1: LineMetaData(0, "foo", 1),
    }
    trace_mock.covered_line_ids = {0}
    assert not ff.compute_line_coverage_fitness_is_covered(trace_mock, subject_properties_mock)


def test_line_coverage_is_covered(subject_properties_mock, trace_mock):
    subject_properties_mock.existing_lines = {
        0: LineMetaData(0, "foo", 0),
        1: LineMetaData(0, "foo", 1),
    }
    trace_mock.covered_line_ids = {0, 1}
    assert ff.compute_line_coverage_fitness_is_covered(trace_mock, subject_properties_mock)


def test_assertion_checked_coverage_none(subject_properties_mock, trace_mock):
    assert ff.compute_assertion_checked_coverage(trace_mock, subject_properties_mock) == 1.0


def test_assertion_checked_coverage_zero(subject_properties_mock, trace_mock):
    subject_properties_mock.existing_lines = {
        0: LineMetaData(0, "foo", 0),
        1: LineMetaData(0, "foo", 1),
    }
    assert ff.compute_assertion_checked_coverage(trace_mock, subject_properties_mock) == 0.0


def test_assertion_checked_coverage_half_covered(subject_properties_mock, trace_mock):
    subject_properties_mock.existing_lines = {
        0: LineMetaData(0, "foo", 0),
        1: LineMetaData(0, "foo", 1),
    }
    executed_assertion = ExecutedAssertion(0, 1, 2, MagicMock())
    trace_mock.executed_assertions = [executed_assertion]
    mock_instr_1 = MagicMock()
    mock_instr_1.lineno = 0
    mock_instr_1.code_object_id = 0
    mock_instr_1.file = "foo"
    with patch.object(AssertionSlicer, "slice_assertion") as slice_mock:
        slice_mock.return_value = [mock_instr_1]
        assert ff.compute_assertion_checked_coverage(trace_mock, subject_properties_mock) == 0.5


def test_assertion_checked_coverage_fully_covered(subject_properties_mock, trace_mock):
    subject_properties_mock.existing_lines = {
        0: LineMetaData(0, "foo", 0),
        1: LineMetaData(0, "foo", 1),
    }
    executed_assertion = ExecutedAssertion(0, 1, 2, MagicMock())
    trace_mock.executed_assertions = [executed_assertion]
    mock_instr_1 = MagicMock()
    mock_instr_1.lineno = 0
    mock_instr_1.code_object_id = 0
    mock_instr_1.file = "foo"
    mock_instr_2 = MagicMock()
    mock_instr_2.lineno = 1
    mock_instr_2.code_object_id = 0
    mock_instr_2.file = "foo"
    with patch.object(AssertionSlicer, "slice_assertion") as slice_mock:
        slice_mock.return_value = [mock_instr_1, mock_instr_2]
        assert ff.compute_assertion_checked_coverage(trace_mock, subject_properties_mock) == 1


def test_statement_checked_coverage_none(subject_properties_mock, trace_mock):
    assert ff.compute_statement_checked_lines([], trace_mock, subject_properties_mock, {}) == set()


def test_statement_checked_coverage_half_covered(subject_properties_mock, trace_mock):
    subject_properties_mock.existing_lines = {
        0: LineMetaData(0, "foo", 0),
        1: LineMetaData(0, "foo", 1),
    }
    mock_instr_1 = MagicMock()
    mock_instr_1.lineno = 0
    mock_instr_1.code_object_id = 0
    mock_instr_1.file = "foo"
    statement = MagicMock()
    statements = [statement]
    with patch.object(DynamicSlicer, "slice") as slice_mock:  # noqa: SIM117
        with patch.object(statement, "get_position") as position_mock:
            position_mock.return_value = 1
            slice_mock.return_value = [mock_instr_1]
            assert ff.compute_statement_checked_lines(
                statements, trace_mock, subject_properties_mock, {1: MagicMock()}
            ) == {0}


def test_statement_checked_coverage_fully_covered(subject_properties_mock, trace_mock):
    subject_properties_mock.existing_lines = {
        0: LineMetaData(0, "foo", 0),
        1: LineMetaData(0, "foo", 1),
    }
    mock_instr_1 = MagicMock()
    mock_instr_1.lineno = 0
    mock_instr_1.code_object_id = 0
    mock_instr_1.file = "foo"
    mock_instr_2 = MagicMock()
    mock_instr_2.lineno = 1
    mock_instr_2.code_object_id = 0
    mock_instr_2.file = "foo"

    statement = MagicMock()
    statements = [statement]
    with patch.object(DynamicSlicer, "slice") as slice_mock:  # noqa: SIM117
        with patch.object(statement, "get_position") as position_mock:
            position_mock.return_value = 1
            slice_mock.return_value = [mock_instr_1, mock_instr_2]
            assert ff.compute_statement_checked_lines(
                statements, trace_mock, subject_properties_mock, {1: MagicMock()}
            ) == {0, 1}


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
    trace_mock.covered_line_ids = OrderedSet([0, 1])
    result.execution_trace = trace_mock
    results.append(result)
    trace = ff.analyze_results(results)
    assert trace == trace_mock
