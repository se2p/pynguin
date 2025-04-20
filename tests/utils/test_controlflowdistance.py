#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT

#  This file is part of Pynguin.
#
#
#  SPDX-License-Identifier: MIT
#
import math

from unittest.mock import MagicMock

import hypothesis.strategies as st
import pytest

from hypothesis import given

from pynguin.instrumentation.tracer import ExecutionTrace
from pynguin.instrumentation.tracer import ExecutionTracer
from pynguin.testcase.execution import ExecutionResult
from pynguin.utils.controlflowdistance import ControlFlowDistance
from pynguin.utils.controlflowdistance import get_root_control_flow_distance


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
def test_calculate_control_flow_distance_for_root(executed_code_objects, approach_level):
    execution_result = MagicMock(ExecutionResult)
    execution_trace = MagicMock(ExecutionTrace)
    execution_trace.executed_code_objects = executed_code_objects
    execution_result.execution_trace = execution_trace
    tracer = ExecutionTracer()
    tracer.register_code_object(MagicMock())
    tracer.register_code_object(MagicMock())

    distance = get_root_control_flow_distance(execution_result, 0, tracer)
    assert distance == ControlFlowDistance(approach_level=approach_level, branch_distance=0.0)
