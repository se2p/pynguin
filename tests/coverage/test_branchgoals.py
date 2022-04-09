#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#

from __future__ import annotations

import importlib
import inspect
import threading
from unittest import mock
from unittest.mock import MagicMock

import pytest

import pynguin.coverage.branchgoals as bg
import pynguin.coverage.controlflowdistance as cfd
import pynguin.ga.testcasechromosome as tcc
import pynguin.testcase.defaulttestcase as dtc
import pynguin.testcase.statement as stmt
import pynguin.utils.generic.genericaccessibleobject as gao
from pynguin.analyses.types import InferredSignature
from pynguin.instrumentation.machinery import install_import_hook
from pynguin.testcase.execution import (
    ExecutionResult,
    ExecutionTrace,
    ExecutionTracer,
    KnownData,
    LineMetaData,
    TestCaseExecutor,
)
from tests.slicer.test_assertionslicer import get_plus_test_with_assertions


@pytest.fixture
def branchless_codeobject_goal():
    return bg.BranchlessCodeObjectGoal(0)


@pytest.fixture
def branch_goal():
    return bg.BranchGoal(0, 0, True)


@pytest.fixture
def statement_coverage_goal():
    return bg.LineCoverageGoal(0, 42)


def test_root_branch_coverage_goal(branchless_codeobject_goal):
    assert branchless_codeobject_goal.code_object_id == 0


def test_non_root_branch_coverage_goal(branch_goal):
    assert branch_goal.predicate_id == 0
    assert branch_goal.value is True


def test_statement_coverage_goal(statement_coverage_goal):
    assert statement_coverage_goal.code_object_id == 0
    assert statement_coverage_goal.line_id == 42


def test_root_hash(branchless_codeobject_goal):
    assert branchless_codeobject_goal.__hash__() != 0


def test_non_root_hash(branch_goal):
    assert branch_goal.__hash__() != 0


def test_statement_coverage_hash(statement_coverage_goal):
    assert statement_coverage_goal.__hash__() != 0


def test_root_eq_same(branchless_codeobject_goal):
    assert branchless_codeobject_goal.__eq__(branchless_codeobject_goal)


def test_non_root_eq_same(branch_goal):
    assert branch_goal.__eq__(branch_goal)


def test_statement_coverage_eq_same(statement_coverage_goal):
    assert statement_coverage_goal.__eq__(statement_coverage_goal)


def test_root_eq_other_type(branchless_codeobject_goal):
    assert not branchless_codeobject_goal.__eq__(MagicMock())


def test_non_root_eq_other_type(branch_goal):
    assert not branch_goal.__eq__(MagicMock())


def test_statement_coverage_eq_other_type(statement_coverage_goal):
    assert not statement_coverage_goal.__eq__(MagicMock())


def test_root_eq_other(branchless_codeobject_goal):
    other = bg.BranchlessCodeObjectGoal(0)
    assert branchless_codeobject_goal.__eq__(other)


def test_non_root_eq_other(branch_goal):
    other = bg.BranchGoal(0, 0, True)
    assert branch_goal.__eq__(other)


def test_statement_coverage_eq_other(statement_coverage_goal):
    other = bg.LineCoverageGoal(0, 42)
    assert statement_coverage_goal.__eq__(other)


def test_root_get_distance(branchless_codeobject_goal, mocker):
    mock = mocker.patch(
        "pynguin.coverage.branchgoals.cfd" ".get_root_control_flow_distance",
        return_value=42,
    )
    distance = branchless_codeobject_goal.get_distance(MagicMock(), MagicMock())
    assert distance == 42
    mock.assert_called_once()


def test_non_root_get_distance(branch_goal, mocker):
    mock = mocker.patch(
        "pynguin.coverage.branchgoals.cfd" ".get_non_root_control_flow_distance",
        return_value=42,
    )
    distance = branch_goal.get_distance(MagicMock(), MagicMock())
    assert distance == 42
    mock.assert_called_once()


@pytest.fixture
def empty_function():
    return bg.BranchCoverageTestFitness(MagicMock(TestCaseExecutor), MagicMock())


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


def test_goal(executor_mock):
    goal = MagicMock(bg.AbstractBranchCoverageGoal)
    func = bg.BranchCoverageTestFitness(executor_mock, goal)
    assert func.goal == goal


def test_compute_fitness_values_mocked(known_data_mock, executor_mock, trace_mock):
    tracer = MagicMock()
    tracer.get_known_data.return_value = known_data_mock
    executor_mock.tracer.return_value = tracer
    goal = MagicMock(bg.AbstractBranchCoverageGoal)
    goal.get_distance.return_value = cfd.ControlFlowDistance(1, 2)
    ff = bg.BranchCoverageTestFitness(executor_mock, goal)
    indiv = MagicMock()
    with mock.patch.object(ff, "_run_test_case_chromosome") as run_suite_mock:
        result = ExecutionResult()
        result.execution_trace = trace_mock
        run_suite_mock.return_value = result
        fitness = ff.compute_fitness(indiv)
        assert fitness == pytest.approx(1.666666)
        run_suite_mock.assert_called_with(indiv)


def test_compute_fitness_values_no_branches():
    module_name = "tests.fixtures.branchcoverage.nobranches"
    tracer = ExecutionTracer()
    tracer.current_thread_identifier = threading.current_thread().ident
    with install_import_hook(module_name, tracer):
        module = importlib.import_module(module_name)
        importlib.reload(module)

        executor = TestCaseExecutor(tracer)
        chromosome = _get_test_for_no_branches_fixture(module)
        pool = bg.BranchGoalPool(tracer.get_known_data())
        goals = bg.create_branch_coverage_fitness_functions(executor, pool)
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
        assert chromosome.get_fitness_for(goals_dict["__init__"]) == 0.0
        assert chromosome.get_fitness_for(goals_dict["other"]) == 1.0
        assert chromosome.get_fitness_for(goals_dict["<module>"]) == 0.0
        assert chromosome.get_fitness_for(goals_dict["get_x"]) == 0.0
        assert chromosome.get_fitness_for(goals_dict["identity"]) == 0.0
        assert chromosome.get_fitness_for(goals_dict["DummyClass"]) == 0.0


def test_compute_fitness_values_single_branches_if():
    module_name = "tests.fixtures.branchcoverage.singlebranches"
    tracer = ExecutionTracer()
    tracer.current_thread_identifier = threading.current_thread().ident
    with install_import_hook(module_name, tracer):
        module = importlib.import_module(module_name)
        importlib.reload(module)

        executor = TestCaseExecutor(tracer)
        chromosome = _get_test_for_single_branch_if_branch_fixture(module)
        pool = bg.BranchGoalPool(tracer.get_known_data())
        goals = bg.create_branch_coverage_fitness_functions(executor, pool)
        for goal in goals:
            chromosome.add_fitness_function(goal)
        fitness = chromosome.get_fitness()
        assert fitness == pytest.approx(0.85714285)


def test_compute_fitness_values_single_branches_else():
    module_name = "tests.fixtures.branchcoverage.singlebranches"
    tracer = ExecutionTracer()
    tracer.current_thread_identifier = threading.current_thread().ident
    with install_import_hook(module_name, tracer):
        module = importlib.import_module(module_name)
        importlib.reload(module)

        executor = TestCaseExecutor(tracer)
        chromosome = _get_test_for_single_branch_else_branch_fixture(module)
        pool = bg.BranchGoalPool(tracer.get_known_data())
        goals = bg.create_branch_coverage_fitness_functions(executor, pool)
        for goal in goals:
            chromosome.add_fitness_function(goal)
        fitness = chromosome.get_fitness()
        assert fitness == pytest.approx(0.85714285)


def test_compute_fitness_values_two_method_single_branches_else():
    module_name = "tests.fixtures.branchcoverage.twomethodsinglebranches"
    tracer = ExecutionTracer()
    tracer.current_thread_identifier = threading.current_thread().ident
    with install_import_hook(module_name, tracer):
        module = importlib.import_module(module_name)
        importlib.reload(module)

        executor = TestCaseExecutor(tracer)
        chromosome = _get_test_for_single_branch_else_branch_fixture(module)
        pool = bg.BranchGoalPool(tracer.get_known_data())
        goals = bg.create_branch_coverage_fitness_functions(executor, pool)
        for goal in goals:
            chromosome.add_fitness_function(goal)
        fitness = chromosome.get_fitness()
        assert fitness == pytest.approx(10.85714285)


def test_compute_fitness_values_nested_branches():
    module_name = "tests.fixtures.branchcoverage.nestedbranches"
    tracer = ExecutionTracer()
    tracer.current_thread_identifier = threading.current_thread().ident
    with install_import_hook(module_name, tracer):
        module = importlib.import_module(module_name)
        importlib.reload(module)

        executor = TestCaseExecutor(tracer)
        chromosome = _get_test_for_nested_branch_fixture(module)
        pool = bg.BranchGoalPool(tracer.get_known_data())
        goals = bg.create_branch_coverage_fitness_functions(executor, pool)
        for goal in goals:
            chromosome.add_fitness_function(goal)
        fitness = chromosome.get_fitness()
        assert fitness == pytest.approx(5.90782493)


def _get_test_for_no_branches_fixture(module) -> tcc.TestCaseChromosome:
    test_case = dtc.DefaultTestCase()
    int_stmt = stmt.IntPrimitiveStatement(test_case, 5)
    function_call = stmt.FunctionStatement(
        test_case,
        gao.GenericFunction(
            module.identity,
            InferredSignature(
                signature=inspect.signature(module.identity),
                parameters={"a": int},
                return_type=int,
            ),
        ),
        {"a": int_stmt.ret_val},
    )
    constructor_call = stmt.ConstructorStatement(
        test_case,
        gao.GenericConstructor(
            module.DummyClass,
            InferredSignature(
                signature=inspect.signature(module.DummyClass.__init__),
                parameters={"x": int},
                return_type=module.DummyClass,
            ),
        ),
        {"x": function_call.ret_val},
    )
    method_call = stmt.MethodStatement(
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
    int_stmt = stmt.IntPrimitiveStatement(test_case, 5)
    function_call = stmt.FunctionStatement(
        test_case,
        gao.GenericFunction(
            module.first,
            InferredSignature(
                signature=inspect.signature(module.first),
                parameters={"a": int},
                return_type=int,
            ),
        ),
        {"a": int_stmt.ret_val},
    )
    test_case.add_statement(int_stmt)
    test_case.add_statement(function_call)
    return tcc.TestCaseChromosome(test_case=test_case)


def _get_test_for_single_branch_else_branch_fixture(module) -> tcc.TestCaseChromosome:
    test_case = dtc.DefaultTestCase()
    int_stmt = stmt.IntPrimitiveStatement(test_case, -5)
    function_call = stmt.FunctionStatement(
        test_case,
        gao.GenericFunction(
            module.first,
            InferredSignature(
                signature=inspect.signature(module.first),
                parameters={"a": int},
                return_type=int,
            ),
        ),
        {"a": int_stmt.ret_val},
    )
    test_case.add_statement(int_stmt)
    test_case.add_statement(function_call)
    return tcc.TestCaseChromosome(test_case=test_case)


def _get_test_for_nested_branch_fixture(module) -> tcc.TestCaseChromosome:
    test_case = dtc.DefaultTestCase()
    int_stmt = stmt.IntPrimitiveStatement(test_case, -50)
    function_call = stmt.FunctionStatement(
        test_case,
        gao.GenericFunction(
            module.nested_branches,
            InferredSignature(
                signature=inspect.signature(module.nested_branches),
                parameters={"a": int},
                return_type=int,
            ),
        ),
        {"a": int_stmt.ret_val},
    )
    test_case.add_statement(int_stmt)
    test_case.add_statement(function_call)
    return tcc.TestCaseChromosome(test_case=test_case)


def test_compute_fitness_values_statement_coverage_empty():
    module_name = "tests.fixtures.linecoverage.emptyfile"
    tracer = ExecutionTracer()
    tracer.current_thread_identifier = threading.current_thread().ident
    with install_import_hook(module_name, tracer):
        module = importlib.import_module(module_name)
        importlib.reload(module)

        executor = TestCaseExecutor(tracer)
        chromosome = _get_empty_test()
        goals = bg.create_line_coverage_fitness_functions(executor)
        assert not goals
        fitness = chromosome.get_fitness()
        assert fitness == 0


def test_statement_coverage_goal_creation(known_data_mock, executor_mock):
    tracer = ExecutionTracer()
    tracer.get_known_data().existing_lines = _get_lines_data_for_plus_module()
    executor_mock.tracer = tracer
    goals = bg.create_line_coverage_fitness_functions(executor_mock)

    assert len(goals) == 8


def test_compute_fitness_values_statement_coverage_non_empty_file_empty_test(
    known_data_mock, executor_mock, trace_mock
):
    """Create an empty test for a non-empty file, which results a fitness of 8, for every missing goal"""
    tracer = ExecutionTracer()
    tracer.get_known_data().existing_lines = _get_lines_data_for_plus_module()

    executor_mock.tracer = tracer
    trace_mock.covered_line_ids = {}

    chromosome = _get_empty_test()
    _add_plus_line_fitness_functions_to_chromosome(chromosome, executor_mock)

    fitness = chromosome.get_fitness()
    assert fitness == 8


def test_compute_fitness_values_statement_coverage_non_empty_file(
    known_data_mock, executor_mock, trace_mock
):
    """
    Test for a testcase for the plus module, which should cover 5 out of 8 goals,
    which results in a fitness value of 8 - 5 = 3

    Generated testcase:
        number = 42
        plus = Plus()
        plus.plus_four(number)
    """
    module_name = "tests.fixtures.linecoverage.plus"

    tracer = ExecutionTracer()
    tracer.get_known_data().existing_lines = _get_lines_data_for_plus_module()

    tracer.current_thread_identifier = threading.current_thread().ident
    executor_mock.tracer = tracer

    with install_import_hook(module_name, tracer):
        module = importlib.import_module(module_name)
        importlib.reload(module)

        chromosome = get_plus_test_with_assertions(module)
        _add_plus_line_fitness_functions_to_chromosome(chromosome, executor_mock)

        with mock.patch.object(
            bg.LineCoverageTestFitness, "_run_test_case_chromosome"
        ) as run_suite_mock:
            result = ExecutionResult()
            trace_mock.covered_line_ids = {0, 1, 5, 6, 7}
            result.execution_trace = trace_mock
            run_suite_mock.return_value = result

            fitness = chromosome.get_fitness()
            assert fitness == 3


def _add_plus_line_fitness_functions_to_chromosome(chromosome, executor_mock):
    lines = [8, 9, 11, 12, 13, 15, 16, 17]
    for line_id in range(len(lines)):
        line_goal = bg.LineCoverageGoal(0, line_id)
        chromosome.add_fitness_function(
            bg.LineCoverageTestFitness(executor_mock, line_goal)
        )


def _get_lines_data_for_plus_module():
    file_name = "../fixtures/linecoverage/plus.py"
    lines = [8, 9, 11, 12, 13, 15, 16, 17]
    return {
        line_id: LineMetaData(0, file_name, lines[line_id])
        for line_id in range(len(lines))
    }


def _get_empty_test() -> tcc.TestCaseChromosome:
    test_case = dtc.DefaultTestCase()
    return tcc.TestCaseChromosome(test_case=test_case)

