#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
import importlib
from logging import Logger
from unittest.mock import MagicMock

import pytest

import pynguin.configuration as config
import pynguin.ga.algorithms.dynamosaalgorithm as dyna
import pynguin.ga.coveragegoals as bg
import pynguin.ga.generationalgorithmfactory as gaf
from pynguin.analyses.module import generate_test_cluster
from pynguin.configuration import ToCoverConfiguration
from pynguin.instrumentation.machinery import install_import_hook
from pynguin.instrumentation.tracer import SubjectProperties
from pynguin.instrumentation.transformer import InstrumentationTransformer
from pynguin.instrumentation.version import (
    BranchCoverageInstrumentation,
    CheckedCoverageInstrumentation,
    LineCoverageInstrumentation,
)
from pynguin.testcase.execution import TestCaseExecutor
from pynguin.utils.orderedset import OrderedSet
from tests.testutils import instrument_function


@pytest.fixture
def dynamosa_subject_properties(subject_properties: SubjectProperties):
    nested_module = importlib.import_module("tests.fixtures.examples.nested")
    importlib.reload(nested_module)

    adapter = BranchCoverageInstrumentation(subject_properties)
    transformer = InstrumentationTransformer(
        subject_properties,
        [adapter],
        to_cover_config=ToCoverConfiguration(enable_inline_pragma_no_cover=False),
    )
    instrument_function(transformer, nested_module.test_me)
    return subject_properties


@pytest.fixture
def dynamosa_subject_properties_nested(subject_properties: SubjectProperties):
    def testMe(_):  # pragma: no cover  # noqa: N802
        def inner(_):
            pass

    adapter = BranchCoverageInstrumentation(subject_properties)
    transformer = InstrumentationTransformer(
        subject_properties,
        [adapter],
        to_cover_config=ToCoverConfiguration(enable_inline_pragma_no_cover=False),
    )
    instrument_function(transformer, testMe)
    return subject_properties


def test_fitness_graph_root_branches(dynamosa_subject_properties):
    pool = bg.BranchGoalPool(dynamosa_subject_properties)
    ffs = bg.create_branch_coverage_fitness_functions(MagicMock(), pool)
    ffgraph = dyna._BranchFitnessGraph(ffs, dynamosa_subject_properties)
    assert {br.goal for br in ffgraph.root_branches} == {
        bg.BranchGoal(code_object_id=0, predicate_id=0, value=False),
        bg.BranchGoal(code_object_id=0, predicate_id=0, value=True),
    }


def test_fitness_graph_structural_children(dynamosa_subject_properties):
    pool = bg.BranchGoalPool(dynamosa_subject_properties)
    ffs = bg.create_branch_coverage_fitness_functions(MagicMock(), pool)
    ffgraph = dyna._BranchFitnessGraph(ffs, dynamosa_subject_properties)
    target = next(
        ff for ff in ffs if ff.goal == bg.BranchGoal(code_object_id=0, predicate_id=2, value=True)
    )
    assert {ff.goal for ff in ffgraph.get_structural_children(target)} == {
        bg.BranchGoal(code_object_id=0, predicate_id=3, value=False),
        bg.BranchGoal(code_object_id=0, predicate_id=3, value=True),
    }


def test_fitness_graph_no_structural_children(dynamosa_subject_properties):
    pool = bg.BranchGoalPool(dynamosa_subject_properties)
    ffs = bg.create_branch_coverage_fitness_functions(MagicMock(), pool)
    ffgraph = dyna._BranchFitnessGraph(ffs, dynamosa_subject_properties)
    target = next(
        ff for ff in ffs if ff.goal == bg.BranchGoal(code_object_id=0, predicate_id=3, value=False)
    )
    assert {ff.goal for ff in ffgraph.get_structural_children(target)} == set()


def test_fitness_graph_nested(dynamosa_subject_properties_nested):
    pool = bg.BranchGoalPool(dynamosa_subject_properties_nested)
    ffs = bg.create_branch_coverage_fitness_functions(MagicMock(), pool)
    ffgraph = dyna._BranchFitnessGraph(ffs, dynamosa_subject_properties_nested)
    assert {ff.goal for ff in ffgraph.root_branches} == {
        bg.BranchlessCodeObjectGoal(0),
        bg.BranchlessCodeObjectGoal(1),
    }


@pytest.fixture
def dynamosa_subject_properties_all(subject_properties: SubjectProperties):
    nested_module = importlib.import_module("tests.fixtures.examples.nested")
    importlib.reload(nested_module)

    adapters = [
        BranchCoverageInstrumentation(subject_properties),
        LineCoverageInstrumentation(subject_properties),
        CheckedCoverageInstrumentation(subject_properties),
    ]
    transformer = InstrumentationTransformer(
        subject_properties,
        adapters,
        to_cover_config=ToCoverConfiguration(enable_inline_pragma_no_cover=False),
    )
    instrument_function(transformer, nested_module.test_me)
    return subject_properties


def test_control_dependency_graph_line_coverage_only(dynamosa_subject_properties_all):
    executor = MagicMock()
    executor.subject_properties = dynamosa_subject_properties_all
    line_ffs = bg.create_line_coverage_fitness_functions(executor)
    graph = dyna._ControlDependencyGraph(line_ffs, dynamosa_subject_properties_all)

    assert graph.root_goals == graph.root_branches
    assert len(graph.root_goals) == len(line_ffs)
    assert graph.root_goals == line_ffs


def test_control_dependency_graph_checked_coverage_only(dynamosa_subject_properties_all):
    executor = MagicMock()
    executor.subject_properties = dynamosa_subject_properties_all
    checked_ffs = bg.create_checked_coverage_fitness_functions(executor)
    graph = dyna._ControlDependencyGraph(checked_ffs, dynamosa_subject_properties_all)

    assert graph.root_goals == graph.root_branches
    assert len(graph.root_goals) == len(checked_ffs)
    assert graph.root_goals == checked_ffs


def test_control_dependency_graph_mixed_coverage(dynamosa_subject_properties_all):
    executor = MagicMock()
    executor.subject_properties = dynamosa_subject_properties_all
    pool = bg.BranchGoalPool(dynamosa_subject_properties_all)
    branch_ffs = bg.create_branch_coverage_fitness_functions(executor, pool)
    line_ffs = bg.create_line_coverage_fitness_functions(executor)
    checked_ffs = bg.create_checked_coverage_fitness_functions(executor)

    all_ffs: OrderedSet[dyna.ff.TestCaseFitnessFunction] = OrderedSet(
        list(branch_ffs) + list(line_ffs) + list(checked_ffs)
    )
    graph = dyna._ControlDependencyGraph(all_ffs, dynamosa_subject_properties_all)

    # Root goals: root branches (predicate 0 True & False) and line/checked goal for line 8
    assert len(graph.root_goals) == 4
    pred0_true = next(ff for ff in branch_ffs if ff.goal == bg.BranchGoal(0, 0, value=True))
    pred0_false = next(ff for ff in branch_ffs if ff.goal == bg.BranchGoal(0, 0, value=False))
    assert pred0_true in graph.root_goals
    assert pred0_false in graph.root_goals

    # Structural children of predicate 0 True: child branches, lines (9, 11), checked (9, 11)
    children = graph.get_structural_children(pred0_true)
    assert len(children) == 8
    # Branches 1 (T, F) and 2 (T, F)
    assert any(
        isinstance(c, bg.BranchCoverageTestFitness) and c.goal.predicate_id == 1 for c in children
    )
    assert any(
        isinstance(c, bg.BranchCoverageTestFitness) and c.goal.predicate_id == 2 for c in children
    )
    # Line and checked coverage goals
    assert any(isinstance(c, bg.LineCoverageTestFitness) for c in children)
    assert any(isinstance(c, bg.StatementCheckedCoverageTestFitness) for c in children)


def test_control_dependency_graph_dot(dynamosa_subject_properties_all, monkeypatch):
    executor = MagicMock()
    executor.subject_properties = dynamosa_subject_properties_all
    line_ffs = bg.create_line_coverage_fitness_functions(executor)
    graph = dyna._ControlDependencyGraph(line_ffs, dynamosa_subject_properties_all)
    mock_pydot = MagicMock()
    mock_pydot.to_string.return_value = "digraph { }"
    monkeypatch.setattr("pynguin.ga.algorithms.dynamosaalgorithm.to_pydot", lambda _: mock_pydot)
    assert "digraph" in graph.dot


def test_goals_manager_mixed_coverage(dynamosa_subject_properties_all):
    executor = MagicMock()
    executor.subject_properties = dynamosa_subject_properties_all
    pool = bg.BranchGoalPool(dynamosa_subject_properties_all)
    branch_ffs = bg.create_branch_coverage_fitness_functions(executor, pool)
    line_ffs = bg.create_line_coverage_fitness_functions(executor)
    checked_ffs = bg.create_checked_coverage_fitness_functions(executor)

    all_ffs: OrderedSet[dyna.ff.TestCaseFitnessFunction] = OrderedSet(
        list(branch_ffs) + list(line_ffs) + list(checked_ffs)
    )
    archive = MagicMock()
    archive.covered_goals = set()
    gm = dyna._GoalsManager(all_ffs, archive, dynamosa_subject_properties_all)

    # Current goals should initially be root goals
    assert len(gm.current_goals) == 4
    pred0_true = next(ff for ff in branch_ffs if ff.goal == bg.BranchGoal(0, 0, value=True))
    assert pred0_true in gm.current_goals

    # Simulate solution covering pred0_true
    def update_side_effect(_):
        archive.covered_goals.add(pred0_true)

    archive.update.side_effect = update_side_effect
    gm.update([MagicMock()])

    # pred0_true covered -> removed from current goals, structural children added
    assert pred0_true not in gm.current_goals
    graph = dyna._ControlDependencyGraph(all_ffs, dynamosa_subject_properties_all)
    children = graph.get_structural_children(pred0_true)
    assert children.issubset(gm.current_goals)


def test_dynamosa_integration_with_branch_and_line_coverage(
    subject_properties: SubjectProperties,
):
    module_name = "tests.fixtures.examples.simple"
    config.configuration.algorithm = config.Algorithm.DYNAMOSA
    config.configuration.search_algorithm.coverage_metrics = [
        config.CoverageMetric.BRANCH,
        config.CoverageMetric.LINE,
    ]
    config.configuration.stopping.maximum_iterations = 2
    config.configuration.module_name = module_name
    config.configuration.search_algorithm.min_initial_tests = 1
    config.configuration.search_algorithm.max_initial_tests = 1
    config.configuration.search_algorithm.population = 2
    config.configuration.test_creation.none_weight = 1
    config.configuration.test_creation.any_weight = 1

    with install_import_hook(module_name, subject_properties):
        with subject_properties.instrumentation_tracer:
            module = importlib.import_module(module_name)
            importlib.reload(module)
        executor = TestCaseExecutor(subject_properties)
        cluster = generate_test_cluster(module_name)
        algo = gaf.TestSuiteGenerationAlgorithmFactory(executor, cluster).get_search_algorithm()
        algo._logger = MagicMock(Logger)
        suite = algo.generate_tests()
        assert suite.size() >= 0
