#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
from unittest import mock
from unittest.mock import MagicMock

import pytest

from pynguin.ga.fitnessfunction import FitnessValues
from pynguin.ga.fitnessfunctions.branchdistancetestcasefitness import (
    BranchDistanceTestCaseFitnessFunction,
)
from pynguin.testcase.execution.executionresult import ExecutionResult
from pynguin.testcase.execution.executiontrace import ExecutionTrace
from pynguin.testcase.execution.executiontracer import KnownData
from pynguin.testcase.execution.testcaseexecutor import TestCaseExecutor


@pytest.fixture()
def executor_mock():
    return MagicMock(TestCaseExecutor)


@pytest.fixture()
def trace_mock():
    return ExecutionTrace()


@pytest.fixture()
def known_data_mock():
    return KnownData()


def test_is_maximisation_function(executor_mock):
    ff = BranchDistanceTestCaseFitnessFunction(executor_mock)
    assert not ff.is_maximisation_function()


def test_compute_fitness_values(known_data_mock, executor_mock, trace_mock):
    tracer = MagicMock()
    tracer.get_known_data.return_value = known_data_mock
    executor_mock.tracer.return_value = tracer
    ff = BranchDistanceTestCaseFitnessFunction(executor_mock)
    indiv = MagicMock()
    with mock.patch.object(ff, "_run_test_case_chromosome") as run_suite_mock:
        result = ExecutionResult()
        result.execution_trace = trace_mock
        run_suite_mock.return_value = result
        assert ff.compute_fitness_values(indiv) == FitnessValues(0, 1)
        run_suite_mock.assert_called_with(indiv)
