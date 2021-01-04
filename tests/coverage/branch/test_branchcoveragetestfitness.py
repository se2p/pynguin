#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
from unittest import mock
from unittest.mock import MagicMock

import pytest

import pynguin.coverage.branch.branchcoveragegoal as bcg
import pynguin.coverage.branch.branchcoveragetestfitness as bctf
import pynguin.coverage.controlflowdistance as cfd
from pynguin.coverage.branch.branchcoveragegoal import BranchCoverageGoal
from pynguin.testcase.execution.executionresult import ExecutionResult
from pynguin.testcase.execution.executiontrace import ExecutionTrace
from pynguin.testcase.execution.executiontracer import KnownData
from pynguin.testcase.execution.testcaseexecutor import TestCaseExecutor


@pytest.fixture
def empty_function():
    return bctf.BranchCoverageTestFitness(
        MagicMock(TestCaseExecutor), MagicMock(BranchCoverageGoal)
    )


@pytest.fixture()
def executor_mock():
    return MagicMock(TestCaseExecutor)


@pytest.fixture()
def trace_mock():
    return ExecutionTrace()


@pytest.fixture()
def known_data_mock():
    return KnownData()


def test_is_maximisation_function(empty_function):
    assert not empty_function.is_maximisation_function()


def test_compute_fitness_values(known_data_mock, executor_mock, trace_mock):
    tracer = MagicMock()
    tracer.get_known_data.return_value = known_data_mock
    executor_mock.tracer.return_value = tracer
    goal = MagicMock(bcg.BranchCoverageGoal)
    goal.get_distance.return_value = cfd.ControlFlowDistance(1, 2)
    ff = bctf.BranchCoverageTestFitness(executor_mock, goal)
    indiv = MagicMock()
    with mock.patch.object(ff, "_run_test_case_chromosome") as run_suite_mock:
        result = ExecutionResult()
        result.execution_trace = trace_mock
        run_suite_mock.return_value = result
        fitness_values = ff.compute_fitness_values(indiv)
        assert fitness_values.coverage == 0
        assert pytest.approx(1.666666, fitness_values.fitness)
        run_suite_mock.assert_called_with(indiv)
