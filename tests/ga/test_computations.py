#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
from unittest.mock import MagicMock
from unittest.mock import patch

import pynguin.ga.computations as ff
import pynguin.ga.testcasechromosome as tcc
import pynguin.ga.testsuitechromosome as tsc

from pynguin.instrumentation.tracer import ExecutionTrace
from pynguin.instrumentation.tracer import SubjectProperties
from pynguin.testcase.execution import ExecutionResult


class DummyTestCaseChromosomeComputation(ff.TestCaseChromosomeComputation):
    pass  # pragma: no cover


class DummyTestSuiteChromosomeComputation(ff.TestSuiteChromosomeComputation):
    pass  # pragma: no cover


def test_run_test_case_chromosome_no_result(
    executor_mock: MagicMock,
    result_mock: MagicMock,
):
    executor_mock.execute.return_value = result_mock
    func = DummyTestCaseChromosomeComputation(executor_mock)
    test_case = tcc.TestCaseChromosome(MagicMock())
    test_case.changed = True
    assert func._run_test_case_chromosome(test_case) == result_mock
    assert test_case.get_last_execution_result() == result_mock


def test_run_test_case_chromosome_has_result(
    executor_mock: MagicMock,
    result_mock: MagicMock,
):
    executor_mock.execute.return_value = result_mock
    func = DummyTestCaseChromosomeComputation(executor_mock)
    test_case = tcc.TestCaseChromosome(MagicMock())
    test_case.changed = False
    test_case.set_last_execution_result(result_mock)
    assert func._run_test_case_chromosome(test_case) == result_mock
    assert test_case.get_last_execution_result() == result_mock


def test_resetting_test_case_chromosome_forces_execution(
    executor_mock: MagicMock,
    result_mock: MagicMock,
):
    executor_mock.execute.return_value = result_mock
    func = DummyTestCaseChromosomeComputation(executor_mock)
    test_case = tcc.TestCaseChromosome(MagicMock())
    test_case.changed = True
    test_case.remove_last_execution_result()
    assert func._run_test_case_chromosome(test_case) == result_mock
    assert test_case.get_last_execution_result() == result_mock


def test_branch_test_case_is_minimizing_function(executor_mock: MagicMock):
    func = ff.BranchDistanceTestCaseFitnessFunction(executor_mock, 0)
    assert not func.is_maximisation_function()


def test_test_case_compute_fitness_values(
    subject_properties: SubjectProperties,
    executor_mock: MagicMock,
    execution_trace: ExecutionTrace,
):
    executor_mock.subject_properties.return_value = subject_properties
    func = ff.BranchDistanceTestCaseFitnessFunction(executor_mock, 0)
    indiv = MagicMock()
    with patch.object(func, "_run_test_case_chromosome") as run_suite_mock:
        result = ExecutionResult()
        result.execution_trace = execution_trace
        run_suite_mock.return_value = result
        assert func.compute_fitness(indiv) == 0
        run_suite_mock.assert_called_with(indiv)


def test_line_test_suite_is_minimizing_function(executor_mock: MagicMock):
    func = ff.LineTestSuiteFitnessFunction(executor_mock)
    assert not func.is_maximisation_function()


def test_checked_test_suite_is_minimizing_function(executor_mock: MagicMock):
    func = ff.StatementCheckedTestSuiteFitnessFunction(executor_mock)
    assert not func.is_maximisation_function()


def test_test_suite_is_maximisation_function(executor_mock: MagicMock):
    func = ff.BranchDistanceTestSuiteFitnessFunction(executor_mock)
    assert not func.is_maximisation_function()


def test_test_suite_compute_branch_distance_fitness_values(
    subject_properties: SubjectProperties,
    executor_mock: MagicMock,
    execution_trace: ExecutionTrace,
):
    executor_mock.subject_properties.return_value = subject_properties
    func = ff.BranchDistanceTestSuiteFitnessFunction(executor_mock)
    indiv = MagicMock()
    with patch.object(func, "_run_test_suite_chromosome") as run_suite_mock:
        result = ExecutionResult()
        result.execution_trace = execution_trace
        run_suite_mock.return_value = [result]
        assert func.compute_fitness(indiv) == 0
        run_suite_mock.assert_called_with(indiv)


def test_test_suite_compute_statements_covered_fitness_values(
    subject_properties: SubjectProperties,
    executor_mock: MagicMock,
    execution_trace: ExecutionTrace,
):
    executor_mock.subject_properties.return_value = subject_properties
    func = ff.LineTestSuiteFitnessFunction(executor_mock)
    indiv = MagicMock()
    with patch.object(func, "_run_test_suite_chromosome") as run_suite_mock:
        result = ExecutionResult()
        result.execution_trace = execution_trace
        run_suite_mock.return_value = [result]
        assert func.compute_fitness(indiv) == 0
        run_suite_mock.assert_called_with(indiv)


def test_test_suite_compute_checked_covered_fitness_values(
    subject_properties: SubjectProperties,
    executor_mock: MagicMock,
    execution_trace: ExecutionTrace,
):
    executor_mock.subject_properties.return_value = subject_properties
    func = ff.StatementCheckedTestSuiteFitnessFunction(executor_mock)
    indiv = MagicMock()
    with patch.object(func, "_run_test_suite_chromosome") as run_suite_mock:
        result = ExecutionResult()
        result.execution_trace = execution_trace
        run_suite_mock.return_value = [result]
        assert func.compute_fitness(indiv) == 0
        run_suite_mock.assert_called_with(indiv)


def test_run_test_suite_chromosome(executor_mock: MagicMock):
    result0 = MagicMock()
    result1 = MagicMock()
    result2 = MagicMock()
    executor_mock.execute_multiple.return_value = [result0, result1]
    ff = DummyTestSuiteChromosomeComputation(executor_mock)
    indiv = tsc.TestSuiteChromosome()
    test_case0 = tcc.TestCaseChromosome(MagicMock())
    test_case0.changed = True
    test_case1 = tcc.TestCaseChromosome(MagicMock())
    test_case1.changed = False
    test_case2 = tcc.TestCaseChromosome(MagicMock())
    test_case2.changed = False
    test_case2.set_last_execution_result(result2)
    indiv.add_test_case_chromosome(test_case0)
    indiv.add_test_case_chromosome(test_case1)
    indiv.add_test_case_chromosome(test_case2)
    assert ff._run_test_suite_chromosome(indiv) == [result0, result1, result2]
    assert test_case0.get_last_execution_result() == result0
    assert test_case1.get_last_execution_result() == result1


def test_run_test_suite_chromosome_cache(executor_mock: MagicMock):
    result0 = MagicMock()
    result1 = MagicMock()
    result2 = MagicMock()
    executor_mock.execute_multiple.return_value = [result0, result1]
    func = DummyTestSuiteChromosomeComputation(executor_mock)
    indiv = tsc.TestSuiteChromosome()
    # Executed because it was changed.
    test_case0 = tcc.TestCaseChromosome(MagicMock())
    test_case0.changed = True
    test_case0.computation_cache._fitness_cache = {"foo": "bar"}
    # Executed because it has no result
    test_case1 = tcc.TestCaseChromosome(MagicMock())
    test_case1.changed = False
    test_case1.computation_cache._fitness_cache = {"foo": "bar"}
    # Not executed.
    test_case2 = tcc.TestCaseChromosome(MagicMock())
    test_case2.changed = False
    test_case2.computation_cache._fitness_cache = {"foo": "bar"}
    test_case2.set_last_execution_result(result2)
    indiv.add_test_case_chromosome(test_case0)
    indiv.add_test_case_chromosome(test_case1)
    indiv.add_test_case_chromosome(test_case2)
    assert func._run_test_suite_chromosome(indiv) == [result0, result1, result2]
    assert test_case0.computation_cache._fitness_cache == {}
    assert test_case1.computation_cache._fitness_cache == {}
    assert test_case2.computation_cache._fitness_cache == {"foo": "bar"}
