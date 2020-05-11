# This file is part of Pynguin.
#
# Pynguin is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Pynguin is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Pynguin.  If not, see <https://www.gnu.org/licenses/>.
from unittest import mock
from unittest.mock import MagicMock

import pytest

from pynguin.ga.fitnessfunction import FitnessValues
from pynguin.ga.fitnessfunctions.branchdistancesuitefitness import (
    BranchDistanceSuiteFitnessFunction,
)
from pynguin.testcase.execution.executionresult import ExecutionResult
from pynguin.testcase.execution.executiontrace import ExecutionTrace
from pynguin.testcase.execution.executiontracer import (
    KnownData,
    CodeObjectMetaData,
    PredicateMetaData,
)
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


def test_default_fitness(executor_mock, trace_mock, known_data_mock):
    ff = BranchDistanceSuiteFitnessFunction(executor_mock)
    assert ff._compute_fitness(trace_mock, known_data_mock) == 0


def test_fitness_function_diff(executor_mock, trace_mock, known_data_mock):
    ff = BranchDistanceSuiteFitnessFunction(executor_mock)
    known_data_mock.existing_code_objects[0] = MagicMock(CodeObjectMetaData)
    known_data_mock.existing_code_objects[1] = MagicMock(CodeObjectMetaData)
    known_data_mock.existing_code_objects[2] = MagicMock(CodeObjectMetaData)
    trace_mock.executed_code_objects.add(0)
    assert ff._compute_fitness(trace_mock, known_data_mock) == 2.0


def test_fitness_covered(executor_mock, trace_mock, known_data_mock):
    ff = BranchDistanceSuiteFitnessFunction(executor_mock)
    known_data_mock.existing_predicates[0] = MagicMock(PredicateMetaData)
    trace_mock.executed_predicates[0] = 1
    trace_mock.false_distances[0] = 1
    trace_mock.true_distances[0] = 0
    assert ff._compute_fitness(trace_mock, known_data_mock) == 1.0


def test_fitness_neither_covered(executor_mock, trace_mock, known_data_mock):
    ff = BranchDistanceSuiteFitnessFunction(executor_mock)
    known_data_mock.existing_predicates[0] = MagicMock(PredicateMetaData)
    assert ff._compute_fitness(trace_mock, known_data_mock) == 2.0


def test_fitness_covered_twice(executor_mock, trace_mock, known_data_mock):
    ff = BranchDistanceSuiteFitnessFunction(executor_mock)
    known_data_mock.existing_predicates[0] = MagicMock(PredicateMetaData)
    trace_mock.executed_predicates[0] = 2
    trace_mock.false_distances[0] = 1
    trace_mock.true_distances[0] = 0
    assert ff._compute_fitness(trace_mock, known_data_mock) == 0.5


def test_fitness_covered_both(executor_mock, trace_mock, known_data_mock):
    ff = BranchDistanceSuiteFitnessFunction(executor_mock)
    known_data_mock.existing_predicates[0] = MagicMock(PredicateMetaData)
    trace_mock.executed_predicates[0] = 2
    trace_mock.false_distances[0] = 0
    trace_mock.true_distances[0] = 0
    assert ff._compute_fitness(trace_mock, known_data_mock) == 0.0


def test_fitness_normalized(executor_mock, trace_mock, known_data_mock):
    ff = BranchDistanceSuiteFitnessFunction(executor_mock)
    known_data_mock.existing_predicates[0] = MagicMock(PredicateMetaData)
    trace_mock.executed_predicates[0] = 2
    trace_mock.false_distances[0] = 0
    trace_mock.true_distances[0] = 7.0
    assert ff._compute_fitness(trace_mock, known_data_mock) == 0.875


def test_is_maximisation_function(executor_mock):
    ff = BranchDistanceSuiteFitnessFunction(executor_mock)
    assert not ff.is_maximisation_function()


@pytest.mark.parametrize("has_ex", [pytest.param(True), pytest.param(False)])
def test_analyze_traces_has_exception(has_ex):
    results = []
    result = MagicMock(ExecutionResult)
    result.has_test_exceptions.return_value = has_ex
    results.append(result)
    has_exception, trace = BranchDistanceSuiteFitnessFunction.analyze_traces(results)
    assert has_ex == has_exception


def test_analyze_traces_empty():
    results = []
    has_exception, trace = BranchDistanceSuiteFitnessFunction.analyze_traces(results)
    assert not has_exception
    assert trace == ExecutionTrace()


def test_analyze_traces_merge(trace_mock):
    results = []
    result = MagicMock(ExecutionResult)
    result.has_test_exceptions.return_value = False
    trace_mock.true_distances[0] = 1
    trace_mock.true_distances[1] = 2
    trace_mock.executed_predicates[0] = 1
    trace_mock.executed_code_objects.add(0)
    result.execution_trace = trace_mock
    results.append(result)
    has_exception, trace = BranchDistanceSuiteFitnessFunction.analyze_traces(results)
    assert not has_exception
    assert trace == trace_mock


def test_worst_fitness(known_data_mock):
    known_data_mock.existing_code_objects[0] = MagicMock(CodeObjectMetaData)
    known_data_mock.existing_predicates[0] = MagicMock(PredicateMetaData)
    assert BranchDistanceSuiteFitnessFunction.get_worst_fitness(known_data_mock) == 3.0


def test_compute_fitness_values(known_data_mock, executor_mock, trace_mock):
    tracer = MagicMock()
    tracer.get_known_data.return_value = known_data_mock
    executor_mock.get_tracer.return_value = tracer
    ff = BranchDistanceSuiteFitnessFunction(executor_mock)
    indiv = MagicMock()
    with mock.patch.object(ff, "_run_test_suite") as run_suite_mock:
        result = ExecutionResult()
        result.execution_trace = trace_mock
        run_suite_mock.return_value = [result]
        assert ff.compute_fitness_values(indiv) == FitnessValues(0, 1)
        run_suite_mock.assert_called_with(indiv)


def test_coverage_none(known_data_mock, executor_mock, trace_mock):
    ff = BranchDistanceSuiteFitnessFunction(executor_mock)
    assert ff._compute_coverage(trace_mock, known_data_mock) == 1.0


def test_coverage_half_branch(known_data_mock, executor_mock, trace_mock):
    ff = BranchDistanceSuiteFitnessFunction(executor_mock)
    known_data_mock.existing_predicates[0] = MagicMock(PredicateMetaData)
    trace_mock.true_distances[0] = 0.0
    assert ff._compute_coverage(trace_mock, known_data_mock) == 0.5


def test_coverage_no_branch(known_data_mock, executor_mock, trace_mock):
    ff = BranchDistanceSuiteFitnessFunction(executor_mock)
    known_data_mock.existing_predicates[0] = MagicMock(PredicateMetaData)
    assert ff._compute_coverage(trace_mock, known_data_mock) == 0.0


def test_coverage_half_code_objects(known_data_mock, executor_mock, trace_mock):
    ff = BranchDistanceSuiteFitnessFunction(executor_mock)
    known_data_mock.existing_code_objects[0] = MagicMock(CodeObjectMetaData)
    known_data_mock.existing_code_objects[1] = MagicMock(CodeObjectMetaData)
    trace_mock.executed_code_objects.add(0)
    assert ff._compute_coverage(trace_mock, known_data_mock) == 0.5


def test_coverage_no_code_objects(known_data_mock, executor_mock, trace_mock):
    ff = BranchDistanceSuiteFitnessFunction(executor_mock)
    known_data_mock.existing_code_objects[0] = MagicMock(CodeObjectMetaData)
    known_data_mock.existing_code_objects[1] = MagicMock(CodeObjectMetaData)
    assert ff._compute_coverage(trace_mock, known_data_mock) == 0.0
