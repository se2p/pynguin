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
from pathlib import Path

from pynguin.refinement.mutation_analyzer import (
    AssertionTracker,
    _assertion_removal_lines,  # noqa: PLC2701
    _AssertionAnalysis,  # noqa: PLC2701
    _build_filtered_test,  # noqa: PLC2701
    _create_mutants,  # noqa: PLC2701
    _evaluate_inferred,  # noqa: PLC2701
    _index_all_assertions,  # noqa: PLC2701
    _killed_set,  # noqa: PLC2701
    _remove_assertion_by_index,  # noqa: PLC2701
    _run_test_against_mutant,  # noqa: PLC2701
    _vacuous_stats,  # noqa: PLC2701
    filter_vacuous_assertions,
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


def test_vacuous_stats_defaults_and_error():
    stats = _vacuous_stats(3, error="failed")
    assert stats["inferred_assertions"] == 3
    assert stats["assertions_kept"] == 3
    assert stats["assertions_removed"] == 0
    assert stats["error"] == "failed"


def test_create_mutants_returns_error_for_module_without_file():
    module = types.ModuleType("no_file")
    module.__file__ = None
    mutants, error = _create_mutants(module, max_mutants=3)
    assert mutants == []
    assert error is not None


def test_create_mutants_returns_error_when_file_missing(tmp_path):
    module = types.ModuleType("missing_file")
    module.__file__ = str(tmp_path / "not_there.py")
    mutants, error = _create_mutants(module, max_mutants=3)
    assert mutants == []
    assert "not found" in (error or "")


def test_index_all_assertions_includes_nested_asserts():
    tree = ast.parse("def test_x():\n    assert a == 1\n    if cond:\n        assert b == 2\n")
    indexed = _index_all_assertions(tree)
    assert indexed == ["a == 1", "b == 2"]


def test_assertion_removal_lines_handles_multiline_assert():
    tree = ast.parse("def test_x():\n    assert (\n        a == 1\n    )\n    assert b == 2\n")
    all_lines, start_lines = _assertion_removal_lines(tree, {0})
    assert 2 in start_lines
    assert all_lines == {2, 3, 4}


def test_build_filtered_test_replaces_removed_assert_with_pass():
    refined = "def test_x():\n    assert (\n        a == 1\n    )\n    assert b == 2\n"
    tree = ast.parse(refined)
    filtered = _build_filtered_test(refined, tree, [0])
    assert "pass" in filtered
    assert "assert b == 2" in filtered


def test_evaluate_inferred_reports_per_test_and_suite_level(monkeypatch):
    refined_test = "def test_x():\n    assert a == 1\n    assert b == 2\n"
    refined_tree = ast.parse(refined_test)

    # Baseline kills {0, 1, 2}; removing first inferred kills only {0, 1},
    # removing second inferred kills {0, 2}.
    responses = iter([
        {0, 1, 2},  # baseline for refined_test
        {0},  # suite baseline from other test
        {0, 1},  # without assertion idx=0
        {0, 2},  # without assertion idx=1
    ])
    monkeypatch.setattr(
        "pynguin.refinement.mutation_analyzer._killed_set",
        lambda *_args, **_kwargs: next(responses),
    )

    analysis = _evaluate_inferred(
        refined_test=refined_test,
        refined_tree=refined_tree,
        inferred_indices=[0, 1],
        mutants=[(object(), None)],
        module_name="mod",
        other_tests_in_suite=["def test_y():\n    assert True\n"],
    )
    assert analysis.to_remove == []
    assert analysis.per_test == {0: 1, 1: 1}
    assert analysis.suite_level == {0: 1, 1: 1}


def test_filter_vacuous_assertions_no_module_returns_error_stats():
    original = "def test_x():\n    assert a == 1\n"
    refined = "def test_x():\n    assert a == 1\n    assert b == 2\n"
    code, stats = filter_vacuous_assertions(original, refined, module_under_test=None)
    assert code == refined
    assert "module source not available" in (stats.get("error") or "")


def test_filter_vacuous_assertions_create_mutants_error(monkeypatch):
    original = "def test_x():\n    assert a == 1\n"
    refined = "def test_x():\n    assert a == 1\n    assert b == 2\n"
    module = types.ModuleType("m")
    module.__file__ = str(Path(__file__))
    monkeypatch.setattr(
        "pynguin.refinement.mutation_analyzer._create_mutants",
        lambda *_args, **_kwargs: ([], "mutant failure"),
    )
    code, stats = filter_vacuous_assertions(original, refined, module_under_test=module)
    assert code == refined
    assert stats["error"] == "mutant failure"


def test_filter_vacuous_assertions_no_mutants(monkeypatch):
    original = "def test_x():\n    assert a == 1\n"
    refined = "def test_x():\n    assert a == 1\n    assert b == 2\n"
    module = types.ModuleType("m")
    module.__file__ = str(Path(__file__))
    monkeypatch.setattr(
        "pynguin.refinement.mutation_analyzer._create_mutants",
        lambda *_args, **_kwargs: ([], None),
    )
    code, stats = filter_vacuous_assertions(original, refined, module_under_test=module)
    assert code == refined
    assert stats["inferred_assertions"] == 1
    assert stats["mutants_generated"] == 0


def test_filter_vacuous_assertions_no_inferred_indices(monkeypatch):
    original = "def test_x():\n    assert a == 1\n"
    refined = "def test_x():\n    assert a == 1\n"
    module = types.ModuleType("m")
    module.__file__ = str(Path(__file__))
    monkeypatch.setattr(
        "pynguin.refinement.mutation_analyzer._create_mutants",
        lambda *_args, **_kwargs: ([(_make_module("m"), None)], None),
    )
    _, stats = filter_vacuous_assertions(original, refined, module_under_test=module)
    assert stats["inferred_assertions"] == 0


def test_filter_vacuous_assertions_removes_non_contributing_assertion(monkeypatch):
    original = "def test_x():\n    assert a == 1\n"
    refined = "def test_x():\n    assert a == 1\n    assert b == 2\n"
    module = types.ModuleType("m")
    module.__file__ = str(Path(__file__))

    monkeypatch.setattr(
        "pynguin.refinement.mutation_analyzer._create_mutants",
        lambda *_args, **_kwargs: ([(_make_module("m"), None)], None),
    )
    monkeypatch.setattr(
        "pynguin.refinement.mutation_analyzer._evaluate_inferred",
        lambda *_args, **_kwargs: _AssertionAnalysis(
            to_remove=[1],
            per_test={1: 0},
            suite_level={1: 0},
            baseline_killed={0},
            suite_baseline_killed=set(),
        ),
    )

    filtered, stats = filter_vacuous_assertions(
        original,
        refined,
        module_under_test=module,
        other_tests_in_suite=["def test_y():\n    assert True\n"],
    )
    assert "pass" in filtered
    assert stats["assertions_removed"] == 1
    assert stats["assertions_kept"] == 0
    assert stats["avg_per_test_contribution"] == 0.0
