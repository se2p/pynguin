#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#

from __future__ import annotations

import ast
import importlib
import threading

from typing import TYPE_CHECKING
from unittest import mock
from unittest.mock import MagicMock

import pytest

import pynguin.ga.coveragegoals as bg
import pynguin.ga.testcasechromosome as tcc
import pynguin.testcase.defaulttestcase as dtc
import pynguin.utils.controlflowdistance as cfd

from pynguin.analyses.constants import EmptyConstantProvider
from pynguin.analyses.module import ModuleTestCluster
from pynguin.analyses.module import generate_test_cluster
from pynguin.analyses.seeding import AstToTestCaseTransformer
from pynguin.instrumentation.machinery import install_import_hook
from pynguin.instrumentation.tracer import ExecutionTrace
from pynguin.instrumentation.tracer import ExecutionTracer
from pynguin.instrumentation.tracer import LineMetaData
from pynguin.instrumentation.tracer import SubjectProperties
from pynguin.testcase.execution import ExecutionResult
from pynguin.testcase.execution import TestCaseExecutor


if TYPE_CHECKING:
    from collections.abc import Callable


@pytest.fixture
def branchless_codeobject_goal():
    return bg.BranchlessCodeObjectGoal(0)


@pytest.fixture
def branch_goal():
    return bg.BranchGoal(code_object_id=0, predicate_id=0, value=True)


@pytest.fixture
def statement_coverage_goal():
    return bg.LineCoverageGoal(code_object_id=0, line_id=42)


def test_root_branch_coverage_goal(branchless_codeobject_goal):
    assert branchless_codeobject_goal.code_object_id == 0


def test_non_root_branch_coverage_goal(branch_goal):
    assert branch_goal.predicate_id == 0
    assert branch_goal.value is True


def test_statement_coverage_goal(statement_coverage_goal):
    assert statement_coverage_goal.code_object_id == 0
    assert statement_coverage_goal.line_id == 42


def test_root_hash(branchless_codeobject_goal):
    assert (hash(branchless_codeobject_goal)) != 0


def test_non_root_hash(branch_goal):
    assert (hash(branch_goal)) != 0


def test_statement_coverage_hash(statement_coverage_goal):
    assert (hash(statement_coverage_goal)) != 0


def test_root_eq_same(branchless_codeobject_goal):
    assert branchless_codeobject_goal == branchless_codeobject_goal  # noqa: PLR0124


def test_non_root_eq_same(branch_goal):
    assert branch_goal == branch_goal  # noqa: PLR0124


def test_statement_coverage_eq_same(statement_coverage_goal):
    assert statement_coverage_goal == statement_coverage_goal  # noqa: PLR0124


def test_root_eq_other_type(branchless_codeobject_goal):
    assert branchless_codeobject_goal != MagicMock()


def test_non_root_eq_other_type(branch_goal):
    assert branch_goal != MagicMock()


def test_statement_coverage_eq_other_type(statement_coverage_goal):
    assert statement_coverage_goal != MagicMock()


def test_root_eq_other(branchless_codeobject_goal):
    other = bg.BranchlessCodeObjectGoal(0)
    assert branchless_codeobject_goal == other


def test_non_root_eq_other(branch_goal):
    other = bg.BranchGoal(code_object_id=0, predicate_id=0, value=True)
    assert branch_goal == other


def test_statement_coverage_eq_other(statement_coverage_goal):
    other = bg.LineCoverageGoal(0, 42)
    assert statement_coverage_goal == other


def test_root_get_distance(branchless_codeobject_goal, mocker):
    mock = mocker.patch(
        "pynguin.ga.coveragegoals.cfd.get_root_control_flow_distance",
        return_value=42,
    )
    distance = branchless_codeobject_goal.get_distance(MagicMock(), MagicMock())
    assert distance == 42
    mock.assert_called_once()


def test_non_root_get_distance(branch_goal, mocker):
    mock = mocker.patch(
        "pynguin.ga.coveragegoals.cfd.get_non_root_control_flow_distance",
        return_value=42,
    )
    distance = branch_goal.get_distance(MagicMock(), MagicMock())
    assert distance == 42
    mock.assert_called_once()


@pytest.fixture
def empty_function():
    return bg.BranchCoverageTestFitness(MagicMock(TestCaseExecutor), MagicMock())


@pytest.fixture
def executor_mock():
    return MagicMock(TestCaseExecutor)


@pytest.fixture
def trace_mock():
    return ExecutionTrace()


@pytest.fixture
def subject_properties_mock():
    return SubjectProperties()


def test_is_maximisation_function(empty_function):
    assert not empty_function.is_maximisation_function()


def test_goal(executor_mock):
    goal = MagicMock(bg.AbstractBranchCoverageGoal)
    func = bg.BranchCoverageTestFitness(executor_mock, goal)
    assert func.goal == goal


def test_compute_fitness_values_mocked(subject_properties_mock, executor_mock, trace_mock):
    tracer = MagicMock()
    tracer.get_subject_properties.return_value = subject_properties_mock
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
        chromosome = _get_test_for_no_branches_fixture(module_name)
        pool = bg.BranchGoalPool(tracer.get_subject_properties())
        goals = bg.create_branch_coverage_fitness_functions(executor, pool)
        goals_dict = {}
        for goal in goals:
            chromosome.add_fitness_function(goal)
            goals_dict[
                tracer.get_subject_properties()
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


def _get_test_for_simple_nesting_no_branch_covered(
    module_name,
) -> tcc.TestCaseChromosome:
    cluster = generate_test_cluster(module_name)
    transformer = AstToTestCaseTransformer(
        cluster,
        False,  # noqa: FBT003
        EmptyConstantProvider(),
    )
    transformer.visit(
        ast.parse(
            """def test_case_0():
    int_0 = 10
    int_1 = 10
    var_0 = module_0.foo(int_0, int_1)
"""
        )
    )
    test_case = transformer.testcases[0]
    return tcc.TestCaseChromosome(test_case=test_case)


def _get_test_for_simple_nesting_outer_branch_covered(
    module_name,
) -> tcc.TestCaseChromosome:
    cluster = generate_test_cluster(module_name)
    transformer = AstToTestCaseTransformer(
        cluster,
        False,  # noqa: FBT003
        EmptyConstantProvider(),
    )
    transformer.visit(
        ast.parse(
            """def test_case_0():
    int_0 = 0
    int_1 = 10
    var_0 = module_0.foo(int_0, int_1)
"""
        )
    )
    test_case = transformer.testcases[0]
    return tcc.TestCaseChromosome(test_case=test_case)


@pytest.mark.parametrize(
    "chrom_factory, expected_fitness",
    [
        pytest.param(_get_test_for_simple_nesting_no_branch_covered, 4.7272727272727275),
        pytest.param(_get_test_for_simple_nesting_outer_branch_covered, 1.4090909090909092),
    ],
)
def test_fitness_simple_nesting(
    chrom_factory: Callable[[str], tcc.TestCaseChromosome], expected_fitness: float
):
    module_name = "tests.fixtures.branchcoverage.simplenesting"
    tracer = ExecutionTracer()
    tracer.current_thread_identifier = threading.current_thread().ident
    with install_import_hook(module_name, tracer):
        module = importlib.import_module(module_name)
        importlib.reload(module)

        executor = TestCaseExecutor(tracer)
        chromosome = chrom_factory(module_name)
        pool = bg.BranchGoalPool(tracer.get_subject_properties())
        goals = bg.create_branch_coverage_fitness_functions(executor, pool)
        goals_dict = {}
        for goal in goals:
            chromosome.add_fitness_function(goal)
            goals_dict[
                tracer.get_subject_properties()
                .existing_code_objects[goal._goal.code_object_id]
                .code_object.co_name
            ] = goal
        fitness = chromosome.get_fitness()
        assert fitness == pytest.approx(expected_fitness)


@pytest.mark.parametrize(
    "module_name, expected_fitness, test_case",
    [
        (
            "tests.fixtures.branchcoverage.singlebranches",
            0.8333333333333334,
            """def test_case_0():
    int_0 = 5
    var_0 = module_0.first(int_0)
""",
        ),
        (
            "tests.fixtures.branchcoverage.singlebranches",
            0.85714285,
            """def test_case_0():
    int_0 = -5
    var_0 = module_0.first(int_0)
""",
        ),
        (
            "tests.fixtures.branchcoverage.twomethodsinglebranches",
            10.85714285,
            """def test_case_0():
    int_0 = -5
    var_0 = module_0.first(int_0)
""",
        ),
        (
            "tests.fixtures.branchcoverage.nestedbranches",
            5.906593406593407,
            """def test_case_0():
    int_0 = -50
    var_0 = module_0.nested_branches(int_0)
""",
        ),
    ],
)
def test_compute_fitness_values_branches(test_case, expected_fitness, module_name):
    tracer = ExecutionTracer()
    tracer.current_thread_identifier = threading.current_thread().ident
    with install_import_hook(module_name, tracer):
        module = importlib.import_module(module_name)
        importlib.reload(module)

        executor = TestCaseExecutor(tracer)

        cluster = generate_test_cluster(module_name)

        transformer = AstToTestCaseTransformer(
            cluster,
            False,  # noqa: FBT003
            EmptyConstantProvider(),
        )
        transformer.visit(ast.parse(test_case))
        test_case = transformer.testcases[0]
        chromosome = tcc.TestCaseChromosome(test_case=test_case)

        pool = bg.BranchGoalPool(tracer.get_subject_properties())
        goals = bg.create_branch_coverage_fitness_functions(executor, pool)
        for goal in goals:
            chromosome.add_fitness_function(goal)
        fitness = chromosome.get_fitness()
        assert fitness == pytest.approx(expected_fitness)


def _get_test_for_no_branches_fixture(module_name) -> tcc.TestCaseChromosome:
    cluster = generate_test_cluster(module_name)

    transformer = AstToTestCaseTransformer(
        cluster,
        False,  # noqa: FBT003
        EmptyConstantProvider(),
    )
    transformer.visit(
        ast.parse(
            """def test_case_0():
    int_0 = 5
    var_0 = module_0.identity(int_0)
    dummy_0 = module_0.DummyClass(var_0)
    var_1 = dummy_0.get_x()
"""
        )
    )
    test_case = transformer.testcases[0]
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


def test_statement_coverage_goal_creation(executor_mock):
    tracer = ExecutionTracer()
    tracer.get_subject_properties().existing_lines = _get_lines_data_for_plus_module()
    executor_mock.tracer = tracer
    goals = bg.create_line_coverage_fitness_functions(executor_mock)

    assert len(goals) == 8


def test_compute_fitness_values_statement_coverage_non_empty_file_empty_test(
    executor_mock, trace_mock
):
    """Create an empty test for a non-empty file.

    Results a fitness of 8, for every missing goal.
    """
    tracer = ExecutionTracer()
    tracer.get_subject_properties().existing_lines = _get_lines_data_for_plus_module()

    executor_mock.tracer = tracer
    trace_mock.covered_line_ids = {}

    chromosome = _get_empty_test()
    _add_plus_line_fitness_functions_to_chromosome(chromosome, executor_mock)

    fitness = chromosome.get_fitness()
    assert fitness == 8


def test_compute_fitness_values_statement_coverage_non_empty_file(
    executor_mock, trace_mock, plus_test_with_object_assertion
):
    """Test for a testcase for the plus module.

    It should cover 5 out of 8 goals, which results in a fitness value of 8 - 5 = 3.

    Generated testcase:
        number = 42
        plus = Plus()
        plus.plus_four(number)
    """
    module_name = "tests.fixtures.linecoverage.plus"

    tracer = ExecutionTracer()
    tracer.get_subject_properties().existing_lines = _get_lines_data_for_plus_module()

    tracer.current_thread_identifier = threading.current_thread().ident
    executor_mock.tracer = tracer

    with install_import_hook(module_name, tracer):
        module = importlib.import_module(module_name)
        importlib.reload(module)

        test_case = plus_test_with_object_assertion
        chromosome = tcc.TestCaseChromosome(test_case=test_case)
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
        chromosome.add_fitness_function(bg.LineCoverageTestFitness(executor_mock, line_goal))


def _get_lines_data_for_plus_module():
    file_name = "../fixtures/linecoverage/plus.py"
    lines = [8, 9, 11, 12, 13, 15, 16, 17]
    return {line_id: LineMetaData(0, file_name, line) for line_id, line in enumerate(lines)}


def _get_empty_test() -> tcc.TestCaseChromosome:
    cluster = ModuleTestCluster(0)
    test_case = dtc.DefaultTestCase(cluster)
    return tcc.TestCaseChromosome(test_case=test_case)
