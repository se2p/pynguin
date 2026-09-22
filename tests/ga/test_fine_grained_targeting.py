#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Tests for fine-grained line targeting and pure statement goal resolution."""

from __future__ import annotations

import ast
import dataclasses
import importlib
import types
from unittest.mock import MagicMock

import pytest
from bytecode import Bytecode

import pynguin.configuration as config
import pynguin.ga.algorithms.dynamosaalgorithm as dyna
from pynguin.analyses.module import overlaps_line_ranges
from pynguin.ga.coveragegoals import (
    BranchGoal,
    BranchGoalPool,
    create_branch_coverage_fitness_functions,
)
from pynguin.instrumentation.controlflow import CFG, ControlDependenceGraph
from pynguin.instrumentation.tracer import CodeObjectMetaData, PredicateMetaData, SubjectProperties
from pynguin.instrumentation.transformer import InstrumentationTransformer
from pynguin.instrumentation.version import BranchCoverageInstrumentation
from pynguin.testcase.execution import ExecutionResult

IF_ELSE_TARGETS_MODULE = "tests.fixtures.instrumentation.if_else_targets"


def test_overlaps_line_ranges_none_or_empty():
    func_ast = ast.parse("def foo(): pass").body[0]
    assert overlaps_line_ranges(None, {1, 2, 3})
    assert overlaps_line_ranges(func_ast, set())


def test_overlaps_line_ranges_matching():
    code = "def foo():\n    x = 1\n    return x"
    func_ast = ast.parse(code).body[0]
    # Line numbers: 1 to 3
    assert overlaps_line_ranges(func_ast, {2})
    assert not overlaps_line_ranges(func_ast, {10, 11})


def test_ensure_controlling_predicates_for_pure_statement():
    subject_props = SubjectProperties()

    code = compile("if x:\n    y = 1", "<string>", "exec")
    bytecode = Bytecode.from_code(code)
    cfg = CFG.from_bytecode(bytecode)
    cdg = ControlDependenceGraph.compute(cfg)

    # Find nodes in CFG
    b_if = next(iter(cfg.graph.nodes))

    code_object_id = 0
    code_meta = CodeObjectMetaData(
        code_object=code,
        parent_code_object_id=None,
        cfg=cfg,
        cdg=cdg,
    )
    subject_props.register_code_object(code_object_id, code_meta)

    # Register predicate on line 1 with is_goal=False (not initially in target range)
    pred_meta = PredicateMetaData(line_no=1, code_object_id=code_object_id, node=b_if)
    pid = subject_props.register_predicate(pred_meta, is_goal=False)

    # Ensure pid is in existing_predicates but not in coverage_predicates
    assert pid in subject_props.existing_predicates
    assert pid not in subject_props.coverage_predicates

    # Call ensure_controlling_predicates_for_lines for pure statement line 2
    subject_props.ensure_controlling_predicates_for_lines({2})

    # Compute branch goals and verify only controlling branch goal exists (True branch)
    goal_pool = BranchGoalPool(subject_props)
    goals = goal_pool.branch_goals
    assert len(goals) == 1
    assert goals[0].value is True


def _instrument_target(
    subject_properties: SubjectProperties, function_name: str, line_range: str
) -> types.FunctionType:
    # Returns a new function so the fixture module itself stays uninstrumented.
    config.configuration.to_cover.only_cover_line_ranges = [line_range]
    transformer = InstrumentationTransformer(
        subject_properties,
        [BranchCoverageInstrumentation(subject_properties)],
        to_cover_config=config.ToCoverConfiguration(only_cover_line_ranges=[line_range]),
    )
    function = getattr(importlib.import_module(IF_ELSE_TARGETS_MODULE), function_name)
    return types.FunctionType(transformer.instrument_code(function.__code__), function.__globals__)


def _goal_lines(
    subject_properties: SubjectProperties, goals: list[BranchGoal]
) -> list[tuple[int, bool]]:
    return sorted(
        (subject_properties.existing_predicates[goal.predicate_id].line_no, goal.value)
        for goal in goals
    )


@pytest.mark.parametrize(
    "function_name, line_range, expected_goals",
    [
        pytest.param("simple", "11", [(9, False)], id="simple"),
        pytest.param("nested", "20", [(18, False)], id="nested"),
        pytest.param("compound_and", "27", [(25, False), (25, False)], id="and"),
        pytest.param("compound_or", "33", [(31, False)], id="or"),
        pytest.param("negated", "39", [(37, True)], id="negated-condition"),
        pytest.param("elif_chain", "56", [(54, False)], id="elif-chain"),
        pytest.param("else_with_loop", "62", [(60, False)], id="else-body-starts-with-loop"),
        pytest.param("else_with_single_if", "70", [(68, False)], id="else-body-is-single-if"),
        pytest.param("else_after_comment", "80", [(77, False)], id="comment-before-else"),
        pytest.param("else_with_pass", "86", [(84, False)], id="else-pass"),
        pytest.param("else_body_no_cover", "108", [], id="else-body-no-cover"),
        pytest.param("loop_else", "93", [], id="loop-else-not-handled"),
        pytest.param("simple", "9-11", [(9, False), (9, True)], id="if-and-else-unchanged"),
        pytest.param(
            "else_with_single_if", "68", [(68, False), (68, True)], id="if-with-else-if-unchanged"
        ),
    ],
)
def test_targeted_else_goals(
    subject_properties: SubjectProperties,
    function_name: str,
    line_range: str,
    expected_goals: list[tuple[int, bool]],
):
    _instrument_target(subject_properties, function_name, line_range)

    goals = BranchGoalPool(subject_properties).branch_goals

    assert _goal_lines(subject_properties, goals) == expected_goals


@pytest.mark.parametrize(
    "function_name, line_range, expected_goals",
    [
        pytest.param("simple", "9", [(9, False), (9, True)], id="simple"),
        pytest.param("nested", "18", [(18, False), (18, True)], id="nested"),
        pytest.param(
            "compound_and", "25", [(25, False), (25, False), (25, True), (25, True)], id="and"
        ),
        pytest.param(
            "compound_or", "31", [(31, False), (31, False), (31, True), (31, True)], id="or"
        ),
        pytest.param("negated", "37", [(37, False), (37, True)], id="negated-condition"),
        pytest.param("elif_chain", "54", [(54, False), (54, True)], id="elif-with-else"),
        pytest.param("else_with_single_if", "71", [(71, False), (71, True)], id="if-inside-else"),
        pytest.param("simple", "9-10", [(9, False), (9, True)], id="range-without-else-line"),
        pytest.param("else_header_no_cover", "112", [], id="else-line-no-cover"),
        pytest.param("elif_chain", "52", [(52, False), (52, True)], id="if-with-elif-unchanged"),
    ],
)
def test_targeted_if_line_goals(
    subject_properties: SubjectProperties,
    function_name: str,
    line_range: str,
    expected_goals: list[tuple[int, bool]],
):
    _instrument_target(subject_properties, function_name, line_range)

    goals = BranchGoalPool(subject_properties).branch_goals

    assert _goal_lines(subject_properties, goals) == expected_goals


@pytest.mark.parametrize(
    "function_name, line_range, else_args, if_args",
    [
        pytest.param("simple", "11", (0,), (1,), id="simple"),
        pytest.param("nested", "20", (1, 0), (1, 1), id="nested"),
        pytest.param("compound_and", "27", (1, 0), (1, 1), id="and"),
        pytest.param("negated", "39", (True,), (False,), id="negated-condition"),
        pytest.param("else_with_loop", "62", (0, [1]), (1, [1]), id="else-body-starts-with-loop"),
    ],
)
def test_targeted_else_goal_is_covered_only_by_else_branch(
    subject_properties: SubjectProperties,
    function_name: str,
    line_range: str,
    else_args: tuple,
    if_args: tuple,
):
    function = _instrument_target(subject_properties, function_name, line_range)
    goals = BranchGoalPool(subject_properties).branch_goals
    tracer = subject_properties.instrumentation_tracer

    def any_goal_covered(args: tuple) -> bool:
        tracer.init_trace()
        with tracer:
            function(*args)
        result = ExecutionResult()
        result.execution_trace = tracer.get_trace()
        return any(goal.is_covered(result) for goal in goals)

    assert any_goal_covered(else_args)
    assert not any_goal_covered(if_args)


def test_targeted_else_in_other_file_has_no_goals(subject_properties: SubjectProperties):
    _instrument_target(subject_properties, "simple", "11")
    else_branch = subject_properties.targeted_else_branches[11]
    subject_properties.targeted_else_branches[11] = dataclasses.replace(
        else_branch, file_name="other.py"
    )

    assert not BranchGoalPool(subject_properties).branch_goals


@pytest.mark.parametrize(
    "line_range, expected_goals",
    [
        pytest.param("20", [(18, False)], id="else-line"),
        pytest.param("18", [(18, False), (18, True)], id="if-line"),
    ],
)
def test_targeted_nested_goals_are_root_goals_for_dynamosa(
    subject_properties: SubjectProperties,
    line_range: str,
    expected_goals: list[tuple[int, bool]],
):
    _instrument_target(subject_properties, "nested", line_range)
    pool = BranchGoalPool(subject_properties)
    fitness_functions = create_branch_coverage_fitness_functions(MagicMock(), pool)

    graph = dyna._BranchFitnessGraph(fitness_functions, subject_properties)

    assert _goal_lines(subject_properties, pool.branch_goals) == expected_goals
    assert {fitness.goal for fitness in graph.root_branches} == set(pool.branch_goals)
