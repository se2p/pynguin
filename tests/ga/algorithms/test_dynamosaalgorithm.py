#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
from __future__ import annotations

import importlib
from logging import Logger
from pathlib import Path
from typing import TYPE_CHECKING, cast
from unittest import mock
from unittest.mock import MagicMock

import pytest

import pynguin.configuration as config
import pynguin.ga.algorithms.dynamosaalgorithm as dyna
import pynguin.ga.coveragegoals as bg
import pynguin.ga.generationalgorithmfactory as gaf
import pynguin.generator as gen
from pynguin.analyses.module import generate_test_cluster
from pynguin.configuration import ToCoverConfiguration
from pynguin.instrumentation.controlflow import BasicBlockNode, ControlDependency
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

if TYPE_CHECKING:
    import types

    from pynguin.instrumentation.tracer import SubjectProperties


@pytest.fixture
def dynamosa_subject_properties(subject_properties: SubjectProperties) -> SubjectProperties:
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
def dynamosa_subject_properties_nested(subject_properties: SubjectProperties) -> SubjectProperties:
    def testMe(_):  # pragma: no cover  # noqa: N802
        def inner(_):
            pass

    adapter = BranchCoverageInstrumentation(subject_properties)
    transformer = InstrumentationTransformer(
        subject_properties,
        [adapter],
        to_cover_config=ToCoverConfiguration(enable_inline_pragma_no_cover=False),
    )
    instrument_function(transformer, cast("types.FunctionType", testMe))
    return subject_properties


def test_fitness_graph_root_branches(dynamosa_subject_properties: SubjectProperties) -> None:
    pool = bg.BranchGoalPool(dynamosa_subject_properties)
    ffs = bg.create_branch_coverage_fitness_functions(MagicMock(), pool)
    ffgraph = dyna._BranchFitnessGraph(ffs, dynamosa_subject_properties)
    assert {br.goal for br in ffgraph.root_branches} == {
        bg.BranchGoal(code_object_id=0, predicate_id=0, value=False),
        bg.BranchGoal(code_object_id=0, predicate_id=0, value=True),
    }


def test_fitness_graph_structural_children(
    dynamosa_subject_properties: SubjectProperties,
) -> None:
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


def test_fitness_graph_no_structural_children(
    dynamosa_subject_properties: SubjectProperties,
) -> None:
    pool = bg.BranchGoalPool(dynamosa_subject_properties)
    ffs = bg.create_branch_coverage_fitness_functions(MagicMock(), pool)
    ffgraph = dyna._BranchFitnessGraph(ffs, dynamosa_subject_properties)
    target = next(
        ff for ff in ffs if ff.goal == bg.BranchGoal(code_object_id=0, predicate_id=3, value=False)
    )
    assert {ff.goal for ff in ffgraph.get_structural_children(target)} == set()


def test_fitness_graph_nested(dynamosa_subject_properties_nested: SubjectProperties) -> None:
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

    # Explicitly check that line 8 goals (line and checked) are root goals and have in_degree == 0
    line8_goals = [
        ff
        for ff in all_ffs
        if isinstance(ff, (bg.LineCoverageTestFitness, bg.StatementCheckedCoverageTestFitness))
        and dynamosa_subject_properties_all.existing_lines[ff.goal.line_id].line_number == 8
    ]
    assert len(line8_goals) == 2
    for g in line8_goals:
        assert g in graph.root_goals
        assert graph._graph.in_degree(g) == 0

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


def test_control_dependency_graph_branch_and_checked_coverage(dynamosa_subject_properties_all):
    executor = MagicMock()
    executor.subject_properties = dynamosa_subject_properties_all
    pool = bg.BranchGoalPool(dynamosa_subject_properties_all)
    branch_ffs = bg.create_branch_coverage_fitness_functions(executor, pool)
    checked_ffs = bg.create_checked_coverage_fitness_functions(executor)

    all_ffs: OrderedSet[dyna.ff.TestCaseFitnessFunction] = OrderedSet(
        list(branch_ffs) + list(checked_ffs)
    )
    graph = dyna._ControlDependencyGraph(all_ffs, dynamosa_subject_properties_all)

    # Root goals: root branches (pred 0 True & False) + checked goal for line 8
    assert len(graph.root_goals) == 3
    pred0_true = next(ff for ff in branch_ffs if ff.goal == bg.BranchGoal(0, 0, value=True))
    pred0_false = next(ff for ff in branch_ffs if ff.goal == bg.BranchGoal(0, 0, value=False))
    assert pred0_true in graph.root_goals
    assert pred0_false in graph.root_goals

    children = graph.get_structural_children(pred0_true)
    assert len(children) == 6
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


def test_control_dependency_graph_with_loop(subject_properties: SubjectProperties):
    def loop_fn(items):
        for x in items:
            if x > 0:
                pass

    adapters = [
        BranchCoverageInstrumentation(subject_properties),
        LineCoverageInstrumentation(subject_properties),
    ]
    transformer = InstrumentationTransformer(
        subject_properties,
        adapters,
        to_cover_config=ToCoverConfiguration(enable_inline_pragma_no_cover=False),
    )
    instrument_function(transformer, loop_fn)

    executor = MagicMock()
    executor.subject_properties = subject_properties
    pool = bg.BranchGoalPool(subject_properties)
    branch_ffs = bg.create_branch_coverage_fitness_functions(executor, pool)
    graph = dyna._ControlDependencyGraph(branch_ffs, subject_properties)

    # For-loop predicate has a self-edge/back-edge (in_degree > 0), but is control-dependent
    # on root, so it must be included in root_goals.
    assert len(graph.root_goals) > 0
    loop_branches = [
        f
        for f in graph.root_goals
        if isinstance(f, bg.BranchCoverageTestFitness) and not f.goal.is_branchless_code_object
    ]
    assert len(loop_branches) > 0
    assert all(graph._graph.in_degree(f) > 0 for f in loop_branches)


def test_fitness_graph_with_untracked_dependency(
    dynamosa_subject_properties: SubjectProperties,
) -> None:
    pool = bg.BranchGoalPool(dynamosa_subject_properties)
    ffs = bg.create_branch_coverage_fitness_functions(MagicMock(), pool)
    co_meta = next(iter(dynamosa_subject_properties.existing_code_objects.values()))
    unknown_node = MagicMock(spec=BasicBlockNode)
    fake_dep = ControlDependency(node=unknown_node, branch_value=True)

    with (
        mock.patch.object(
            co_meta.cdg, "get_control_dependencies", return_value=OrderedSet([fake_dep])
        ),
        mock.patch.object(co_meta.cdg, "is_control_dependent_on_root", return_value=False),
    ):
        ffgraph = dyna._BranchFitnessGraph(ffs, dynamosa_subject_properties)
        assert len(ffgraph.root_branches) > 0


def test_fitness_graph_with_pragma_no_cover(subject_properties: SubjectProperties) -> None:
    no_cover_module = importlib.import_module("tests.fixtures.examples.no_cover_example")
    adapter = BranchCoverageInstrumentation(subject_properties)
    transformer = InstrumentationTransformer(
        subject_properties,
        [adapter],
        to_cover_config=ToCoverConfiguration(enable_inline_pragma_no_cover=True),
    )
    instrument_function(transformer, no_cover_module.no_cover_double_if)
    pool = bg.BranchGoalPool(subject_properties)
    ffs = bg.create_branch_coverage_fitness_functions(MagicMock(), pool)
    ffgraph = dyna._BranchFitnessGraph(ffs, subject_properties)
    assert len(ffgraph.root_branches) == 2


def test_dynamosa_integration_with_no_cover(tmp_path: Path) -> None:
    project_path = Path().absolute()
    if project_path.name == "tests":
        project_path /= ".."  # pragma: no cover
    project_path = project_path / "tests" / "fixtures" / "examples"
    configuration = config.Configuration(
        algorithm=config.Algorithm.DYNAMOSA,
        stopping=config.StoppingConfiguration(maximum_search_time=1),
        module_name="no_cover_example",
        test_case_output=config.TestCaseOutputConfiguration(output_path=str(tmp_path)),
        project_path=str(project_path),
        statistics_output=config.StatisticsOutputConfiguration(
            report_dir=str(tmp_path), statistics_backend=config.StatisticsBackend.NONE
        ),
    )
    gen.set_configuration(configuration)
    result = gen.run_pynguin()
    assert result == gen.ReturnCode.OK
