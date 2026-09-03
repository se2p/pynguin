#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Tests for fine-grained line targeting and pure statement goal resolution."""

from __future__ import annotations

import ast

from bytecode import Bytecode

from pynguin.analyses.module import overlaps_line_ranges
from pynguin.ga.coveragegoals import BranchGoalPool
from pynguin.instrumentation.controlflow import CFG, ControlDependenceGraph
from pynguin.instrumentation.tracer import CodeObjectMetaData, PredicateMetaData, SubjectProperties


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
