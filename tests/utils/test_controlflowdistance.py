#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT

#  This file is part of Pynguin.
#
#
#  SPDX-License-Identifier: MIT
#
import importlib
import math
from unittest.mock import MagicMock

import hypothesis.strategies as st
import pytest
from hypothesis import given

import pynguin.configuration as config
from pynguin.instrumentation.machinery import install_import_hook
from pynguin.instrumentation.tracer import ExecutionTrace, LineMetaData, SubjectProperties
from pynguin.testcase.execution import ExecutionResult
from pynguin.utils.controlflowdistance import (
    ControlFlowDistance,
    get_line_control_flow_distance,
    get_root_control_flow_distance,
)
from tests.fixtures.branchcoverage import singlebranches


@pytest.fixture(scope="module")
def control_flow_distance() -> ControlFlowDistance:
    return ControlFlowDistance()


def test_eq_same(control_flow_distance):
    assert control_flow_distance == control_flow_distance  # noqa: PLR0124


def test_eq_other_type(control_flow_distance):
    assert control_flow_distance != MagicMock()


def test_eq_other_value():
    control_flow_distance = ControlFlowDistance()
    other = ControlFlowDistance()
    assert control_flow_distance == other


def test_lt_other_type(control_flow_distance):
    with pytest.raises(TypeError):
        control_flow_distance < MagicMock()  # noqa: B015


@pytest.mark.parametrize(
    "approach_level_1, branch_distance_1, approach_level_2, branch_distance_2, result",
    [
        pytest.param(1, 2, 1, 2, False),
        pytest.param(1, 2, 2, 1, True),
        pytest.param(1, 2, 1, 3, True),
        pytest.param(2, 1, 1, 2, False),
    ],
)
def test_lt(approach_level_1, branch_distance_1, approach_level_2, branch_distance_2, result):
    cfd_1 = ControlFlowDistance(approach_level=approach_level_1, branch_distance=branch_distance_1)
    cfd_2 = ControlFlowDistance(approach_level=approach_level_2, branch_distance=branch_distance_2)
    assert (cfd_1 < cfd_2) == result


@given(level=st.integers(min_value=0))
def test_approach_level(level, control_flow_distance):
    control_flow_distance.approach_level = level
    assert control_flow_distance.approach_level == level


@given(branch_distance=st.floats(min_value=0.0))
def test_branch_distance(branch_distance, control_flow_distance):
    control_flow_distance.branch_distance = branch_distance
    assert control_flow_distance.branch_distance == branch_distance


def test_init_negative_approach_level():
    with pytest.raises(AssertionError):
        ControlFlowDistance(approach_level=-1)


def test_init_negative_branch_distance():
    with pytest.raises(AssertionError):
        ControlFlowDistance(branch_distance=-1)


def test_negative_approach_level(control_flow_distance):
    with pytest.raises(AssertionError):
        control_flow_distance.approach_level = -1


def test_negative_branch_distance(control_flow_distance):
    with pytest.raises(AssertionError):
        control_flow_distance.branch_distance = -1


@given(level=st.integers(min_value=0))
def test_increase_approach_level(level, control_flow_distance):
    control_flow_distance.approach_level = level
    control_flow_distance.increase_approach_level()
    assert control_flow_distance.approach_level == level + 1


@given(level=st.integers(min_value=0), distance=st.floats(min_value=0.0))
def test_get_resulting_branch_fitness(level, distance, control_flow_distance):
    control_flow_distance.approach_level = level
    control_flow_distance.branch_distance = distance

    expected = level + distance / (1.0 + distance) if not math.isinf(distance) else level + 1.0

    assert pytest.approx(control_flow_distance.get_resulting_branch_fitness()) == expected


@pytest.mark.parametrize(
    "executed_code_objects, approach_level",
    [pytest.param([0, 1], 0), pytest.param([1], 1)],
)
def test_calculate_control_flow_distance_for_root(
    executed_code_objects, approach_level, subject_properties: SubjectProperties
):
    execution_result = MagicMock(ExecutionResult)
    execution_trace = MagicMock(ExecutionTrace)
    execution_trace.executed_code_objects = executed_code_objects
    execution_result.execution_trace = execution_trace
    subject_properties.register_code_object(0, MagicMock())
    subject_properties.register_code_object(1, MagicMock())

    distance = get_root_control_flow_distance(execution_result, 0, subject_properties)
    assert distance == ControlFlowDistance(approach_level=approach_level, branch_distance=0.0)


def test_get_line_control_flow_distance_unknown_line(subject_properties: SubjectProperties):
    execution_result = MagicMock(ExecutionResult)
    distance = get_line_control_flow_distance(execution_result, 999, subject_properties)
    assert distance == ControlFlowDistance(approach_level=1, branch_distance=0.0)


def test_get_line_control_flow_distance_unknown_code_object(subject_properties: SubjectProperties):
    execution_result = MagicMock(ExecutionResult)
    subject_properties.existing_lines[0] = LineMetaData(0, "test.py", 10)
    distance = get_line_control_flow_distance(execution_result, 0, subject_properties)
    assert distance == ControlFlowDistance(approach_level=1, branch_distance=0.0)


@pytest.mark.parametrize(
    "executed_code_objects, expected_approach",
    [
        pytest.param([0], 1),
        pytest.param([], 2),
    ],
)
def test_get_line_control_flow_distance_branchless(
    executed_code_objects,
    expected_approach,
    subject_properties: SubjectProperties,
):
    execution_result = MagicMock(ExecutionResult)
    execution_trace = MagicMock(ExecutionTrace)
    execution_trace.executed_code_objects = set(executed_code_objects)
    execution_result.execution_trace = execution_trace

    subject_properties.register_code_object(0, MagicMock())
    subject_properties.existing_lines[0] = LineMetaData(0, "test.py", 10)

    distance = get_line_control_flow_distance(execution_result, 0, subject_properties)
    assert distance == ControlFlowDistance(approach_level=expected_approach, branch_distance=0.0)


def test_get_line_control_flow_distance_with_branches(subject_properties: SubjectProperties):
    module_name = "tests.fixtures.branchcoverage.singlebranches"
    with (
        install_import_hook(
            module_name,
            subject_properties,
            coverage_metrics=(config.CoverageMetric.BRANCH, config.CoverageMetric.LINE),
        ),
        subject_properties.instrumentation_tracer,
    ):
        importlib.reload(singlebranches)

    # Line 10 (root dependent in `first`), Line 11 (True branch), Line 12 (False branch)
    line_11_id = next(
        lid for lid, meta in subject_properties.existing_lines.items() if meta.line_number == 11
    )

    # 1. Empty execution trace (first() was not called)
    res_empty = ExecutionResult()
    dist_empty = get_line_control_flow_distance(res_empty, line_11_id, subject_properties)
    assert dist_empty.approach_level > 1

    # 2. Trace from first(-5): True branch has distance 6.0
    res_neg5 = ExecutionResult()
    with subject_properties.instrumentation_tracer:
        singlebranches.first(-5)
    res_neg5.execution_trace = subject_properties.instrumentation_tracer.get_trace()
    dist_neg5 = get_line_control_flow_distance(res_neg5, line_11_id, subject_properties)
    assert dist_neg5.approach_level == 1
    assert dist_neg5.branch_distance == pytest.approx(6.0)

    # 3. Trace from first(-1): True branch has distance 2.0 (closer!)
    subject_properties.instrumentation_tracer.reset()
    res_neg1 = ExecutionResult()
    with subject_properties.instrumentation_tracer:
        singlebranches.first(-1)
    res_neg1.execution_trace = subject_properties.instrumentation_tracer.get_trace()
    dist_neg1 = get_line_control_flow_distance(res_neg1, line_11_id, subject_properties)
    assert dist_neg1.approach_level == 1
    assert dist_neg1.branch_distance == pytest.approx(2.0)
    assert dist_neg1 < dist_neg5
