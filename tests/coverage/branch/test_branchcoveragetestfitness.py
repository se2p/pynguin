#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
import importlib
from unittest import mock
from unittest.mock import MagicMock

import pytest

import pynguin.coverage.branch.branchcoveragefactory as bcf
import pynguin.coverage.branch.branchcoveragegoal as bcg
import pynguin.coverage.branch.branchcoveragetestfitness as bctf
import pynguin.coverage.controlflowdistance as cfd
import pynguin.ga.testcasechromosome as tcc
import pynguin.testcase.defaulttestcase as dtc
import pynguin.testcase.statements.parametrizedstatements as param_stmt
import pynguin.testcase.statements.primitivestatements as prim_stmt
import pynguin.utils.generic.genericaccessibleobject as gao
from pynguin.instrumentation.machinery import install_import_hook
from pynguin.testcase.execution.executionresult import ExecutionResult
from pynguin.testcase.execution.executiontrace import ExecutionTrace
from pynguin.testcase.execution.executiontracer import ExecutionTracer, KnownData
from pynguin.testcase.execution.testcaseexecutor import TestCaseExecutor
from pynguin.typeinference.strategy import InferredSignature


@pytest.fixture
def empty_function():
    return bctf.BranchCoverageTestFitness(MagicMock(TestCaseExecutor), MagicMock())


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


def test_compute_fitness_values_mocked(known_data_mock, executor_mock, trace_mock):
    tracer = MagicMock()
    tracer.get_known_data.return_value = known_data_mock
    executor_mock.tracer.return_value = tracer
    goal = MagicMock(bcg.AbstractBranchCoverageGoal)
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


def test_compute_fitness_values_no_branches():
    module_name = "tests.fixtures.branchcoverage.nobranches"
    tracer = ExecutionTracer()
    with install_import_hook(module_name, tracer):
        module = importlib.import_module(module_name)
        importlib.reload(module)

        executor = TestCaseExecutor(tracer)
        chromosome = _get_test_for_no_branches_fixture(module)
        goals = bcf.BranchCoverageFactory(executor).get_coverage_goals()
        goals_dict = {}
        for goal in goals:
            chromosome.add_fitness_function(goal)
            goals_dict[
                tracer.get_known_data()
                .existing_code_objects[goal._goal.code_object_id]
                .code_object.co_name
            ] = goal
        fitness = chromosome.get_fitness()
        assert fitness == 1
        assert chromosome.fitness_values[goals_dict["__init__"]].fitness == 0.0
        assert chromosome.fitness_values[goals_dict["other"]].fitness == 1.0
        assert chromosome.fitness_values[goals_dict["<module>"]].fitness == 0.0
        assert chromosome.fitness_values[goals_dict["get_x"]].fitness == 0.0
        assert chromosome.fitness_values[goals_dict["identity"]].fitness == 0.0
        assert chromosome.fitness_values[goals_dict["DummyClass"]].fitness == 0.0


def test_compute_fitness_values_single_branches_if():
    module_name = "tests.fixtures.branchcoverage.singlebranches"
    tracer = ExecutionTracer()
    tracer.reset()
    with install_import_hook(module_name, tracer):
        module = importlib.import_module(module_name)
        importlib.reload(module)

        executor = TestCaseExecutor(tracer)
        chromosome = _get_test_for_single_branch_if_branch_fixture(module)
        goals = bcf.BranchCoverageFactory(executor).get_coverage_goals()
        for goal in goals:
            chromosome.add_fitness_function(goal)
        fitness = chromosome.get_fitness()
        assert fitness == pytest.approx(0.85714285)


def test_compute_fitness_values_single_branches_else():
    module_name = "tests.fixtures.branchcoverage.singlebranches"
    tracer = ExecutionTracer()
    tracer.reset()
    with install_import_hook(module_name, tracer):
        module = importlib.import_module(module_name)
        importlib.reload(module)

        executor = TestCaseExecutor(tracer)
        chromosome = _get_test_for_single_branch_else_branch_fixture(module)
        goals = bcf.BranchCoverageFactory(executor).get_coverage_goals()
        for goal in goals:
            chromosome.add_fitness_function(goal)
        fitness = chromosome.get_fitness()
        assert fitness == pytest.approx(0.85714285)


def test_compute_fitness_values_two_method_single_branches_else():
    module_name = "tests.fixtures.branchcoverage.twomethodsinglebranches"
    tracer = ExecutionTracer()
    tracer.reset()
    with install_import_hook(module_name, tracer):
        module = importlib.import_module(module_name)
        importlib.reload(module)

        executor = TestCaseExecutor(tracer)
        chromosome = _get_test_for_single_branch_else_branch_fixture(module)
        goals = bcf.BranchCoverageFactory(executor).get_coverage_goals()
        for goal in goals:
            chromosome.add_fitness_function(goal)
        fitness = chromosome.get_fitness()
        assert fitness == pytest.approx(10.85714285)


def test_compute_fitness_values_nested_branches():
    module_name = "tests.fixtures.branchcoverage.nestedbranches"
    tracer = ExecutionTracer()
    tracer.reset()
    with install_import_hook(module_name, tracer):
        module = importlib.import_module(module_name)
        importlib.reload(module)

        executor = TestCaseExecutor(tracer)
        chromosome = _get_test_for_nested_branch_fixture(module)
        goals = bcf.BranchCoverageFactory(executor).get_coverage_goals()
        for goal in goals:
            chromosome.add_fitness_function(goal)
        fitness = chromosome.get_fitness()
        assert fitness == pytest.approx(5.90782493)


def _get_test_for_no_branches_fixture(module) -> tcc.TestCaseChromosome:
    test_case = dtc.DefaultTestCase()
    int_stmt = prim_stmt.IntPrimitiveStatement(test_case, 5)
    function_call = param_stmt.FunctionStatement(
        test_case,
        gao.GenericFunction(
            module.identity,
            InferredSignature(signature=MagicMock(), parameters={}, return_type=int),
        ),
        [int_stmt.ret_val],
    )
    constructor_call = param_stmt.ConstructorStatement(
        test_case,
        gao.GenericConstructor(
            module.DummyClass,
            InferredSignature(
                signature=MagicMock(), parameters={}, return_type=module.DummyClass
            ),
        ),
        [function_call.ret_val],
    )
    method_call = param_stmt.MethodStatement(
        test_case,
        gao.GenericMethod(
            module.DummyClass,
            module.DummyClass.get_x,
            InferredSignature(signature=MagicMock(), parameters={}, return_type=int),
        ),
        constructor_call.ret_val,
    )
    test_case.add_statement(int_stmt)
    test_case.add_statement(function_call)
    test_case.add_statement(constructor_call)
    test_case.add_statement(method_call)
    return tcc.TestCaseChromosome(test_case=test_case)


def _get_test_for_single_branch_if_branch_fixture(module) -> tcc.TestCaseChromosome:
    test_case = dtc.DefaultTestCase()
    int_stmt = prim_stmt.IntPrimitiveStatement(test_case, 5)
    function_call = param_stmt.FunctionStatement(
        test_case,
        gao.GenericFunction(
            module.first,
            InferredSignature(signature=MagicMock(), parameters={}, return_type=int),
        ),
        [int_stmt.ret_val],
    )
    test_case.add_statement(int_stmt)
    test_case.add_statement(function_call)
    return tcc.TestCaseChromosome(test_case=test_case)


def _get_test_for_single_branch_else_branch_fixture(module) -> tcc.TestCaseChromosome:
    test_case = dtc.DefaultTestCase()
    int_stmt = prim_stmt.IntPrimitiveStatement(test_case, -5)
    function_call = param_stmt.FunctionStatement(
        test_case,
        gao.GenericFunction(
            module.first,
            InferredSignature(signature=MagicMock(), parameters={}, return_type=int),
        ),
        [int_stmt.ret_val],
    )
    test_case.add_statement(int_stmt)
    test_case.add_statement(function_call)
    return tcc.TestCaseChromosome(test_case=test_case)


def _get_test_for_nested_branch_fixture(module) -> tcc.TestCaseChromosome:
    test_case = dtc.DefaultTestCase()
    int_stmt = prim_stmt.IntPrimitiveStatement(test_case, -50)
    function_call = param_stmt.FunctionStatement(
        test_case,
        gao.GenericFunction(
            module.nested_branches,
            InferredSignature(signature=MagicMock(), parameters={}, return_type=int),
        ),
        [int_stmt.ret_val],
    )
    test_case.add_statement(int_stmt)
    test_case.add_statement(function_call)
    return tcc.TestCaseChromosome(test_case=test_case)
