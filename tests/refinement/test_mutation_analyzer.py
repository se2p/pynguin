#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Tests for mutation-based assertion filtering helpers (mutation_analyzer.py)."""

from __future__ import annotations

import ast
import types

from pynguin.refinement.mutation_analyzer import (
    AssertionTracker,
    _killed_set,
    _remove_assertion_by_index,
    _run_test_against_mutant,
)


def _make_module(name: str, **attrs) -> types.ModuleType:
    module = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(module, key, value)
    return module


def test_assertion_tracker_identifies_inferred_assertions():
    original = "def test():\n    assert x == 1\n"
    refined = "def test():\n    assert x == 1\n    assert isinstance(x, int)\n"
    tracker = AssertionTracker(original, refined)
    assert tracker.original_assertions == ["x == 1"]
    assert "isinstance(x, int)" in tracker.refined_assertions
    assert tracker.inferred_assertions == ["isinstance(x, int)"]


def test_assertion_tracker_no_new_assertions():
    code = "def test():\n    assert a\n"
    tracker = AssertionTracker(code, code)
    assert tracker.inferred_assertions == []


def test_assertion_tracker_handles_unparseable_code():
    tracker = AssertionTracker("def broken(:", "def test():\n    assert a\n")
    assert tracker.original_assertions == []


def test_remove_assertion_by_index_replaces_target():
    tree = ast.parse("def test():\n    assert a == 1\n    assert b == 2\n")
    new_tree = _remove_assertion_by_index(tree, 0)
    asserts = [node for node in ast.walk(new_tree) if isinstance(node, ast.Assert)]
    assert len(asserts) == 1
    assert ast.unparse(asserts[0].test) == "b == 2"


def test_run_test_against_mutant_survives_when_test_passes():
    mutant = _make_module("fakemod", value=1)
    code = "def test_x():\n    assert fakemod.value == 1\n"
    assert _run_test_against_mutant(code, mutant, "fakemod") is False


def test_run_test_against_mutant_killed_when_test_fails():
    mutant = _make_module("fakemod", value=2)
    code = "def test_x():\n    assert fakemod.value == 1\n"
    assert _run_test_against_mutant(code, mutant, "fakemod") is True


def test_killed_set_reports_killed_indices():
    code = "def test_x():\n    assert fakemod.value == 1\n"
    mutants = [
        (_make_module("fakemod", value=2), None),  # killed
        (_make_module("fakemod", value=1), None),  # survives
        (None, None),  # skipped
    ]
    assert _killed_set(code, mutants, "fakemod") == {0}
