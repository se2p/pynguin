#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Tests for mutation-based assertion filtering helpers (mutation_analyzer.py)."""

from __future__ import annotations

import ast
import importlib
import types
from pathlib import Path

import pynguin.configuration as config
from pynguin.assertion.mutation_analysis.controller import MutationController
from pynguin.refinement.mutation_analyzer import (
    AssertionTracker,
    _assertion_removal_lines,  # noqa: PLC2701
    _AssertionAnalysis,  # noqa: PLC2701
    _build_filtered_test,  # noqa: PLC2701
    _evaluate_inferred,  # noqa: PLC2701
    _index_all_assertions,  # noqa: PLC2701
    _remove_assertion_by_index,  # noqa: PLC2701
    _run_test_against_mutant,  # noqa: PLC2701
    _vacuous_stats,  # noqa: PLC2701
    create_mutants,
    evaluate_refined_suite_mutations,
    filter_vacuous_assertions,
    get_surviving_mutants,
    killed_set,
    passes_on_module,
    rank_mutations,
    strip_redundant_pass_statements,
)
from pynguin.refinement.validator import TestExecution
from pynguin.utils.timeout import TestExecutionTimeoutError


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


def test_run_test_against_mutant_runs_every_test_function():
    mutant = _make_module("fakemod", value=2)
    code = (
        "def test_a():\n    assert fakemod.value > 0\n\n"
        "def test_b():\n    assert fakemod.value == 1\n"
    )
    assert _run_test_against_mutant(code, mutant, "fakemod") is True


def test_run_test_against_mutant_expected_xfail_is_not_a_kill():
    mutant = _make_module("fakemod", value=1)
    code = (
        "import pytest\n\n"
        "@pytest.mark.xfail(strict=True)\n"
        "def test_raises():\n    raise ValueError\n\n"
        "def test_value():\n    assert fakemod.value == 1\n"
    )
    assert _run_test_against_mutant(code, mutant, "fakemod") is False


def test_run_test_against_mutant_xfail_does_not_hide_later_tests():
    mutant = _make_module("fakemod", value=2)
    code = (
        "import pytest\n\n"
        "@pytest.mark.xfail(strict=True)\n"
        "def test_raises():\n    raise ValueError\n\n"
        "def test_value():\n    assert fakemod.value == 1\n"
    )
    assert _run_test_against_mutant(code, mutant, "fakemod") is True


def test_run_test_against_mutant_strict_xpass_is_a_kill():
    mutant = _make_module("fakemod", value=2)
    code = (
        "import pytest\n\n"
        "@pytest.mark.xfail(strict=True)\n"
        "def test_raises():\n    assert fakemod.value == 2\n"
    )
    assert _run_test_against_mutant(code, mutant, "fakemod") is True


def test_passes_on_module():
    module = _make_module("fakemod", value=1)
    assert passes_on_module("def test_x():\n    assert fakemod.value == 1\n", module)
    assert not passes_on_module("def test_x():\n    assert fakemod.value == 2\n", module)


def test_passes_on_module_timeout_is_not_a_pass(monkeypatch):
    def time_out(*_args):
        raise TestExecutionTimeoutError

    monkeypatch.setattr("pynguin.refinement.mutation_analyzer.call_test_functions", time_out)
    module = _make_module("fakemod", value=1)
    assert not passes_on_module("def test_x():\n    pass\n", module)


def test_passes_on_module_limits_each_test_not_the_whole_module(monkeypatch):
    # Three tests of 0.3 s each pass a 0.5 s limit one by one, not as a module.
    monkeypatch.setattr(config.configuration.stopping, "maximum_test_execution_timeout", 0.5)
    module = _make_module("fakemod", value=1)
    code = "import time\n" + "".join(
        f"def test_{i}():\n    time.sleep(0.3)\n    assert fakemod.value == 1\n" for i in range(3)
    )
    assert passes_on_module(code, module)
    assert not passes_on_module(code.replace("0.3", "0.7"), module)


def test_killed_set_reports_killed_indices():
    code = "def test_x():\n    assert fakemod.value == 1\n"
    mutants = [
        (_make_module("fakemod", value=2), None),  # killed
        (_make_module("fakemod", value=1), None),  # survives
        (None, None),  # skipped
    ]
    assert killed_set(code, mutants, "fakemod") == {0}


def test_vacuous_stats_defaults_and_error():
    stats = _vacuous_stats(3, error="failed")
    assert stats["inferred_assertions"] == 3
    assert stats["assertions_kept"] == 3
    assert stats["assertions_removed"] == 0
    assert stats["error"] == "failed"


def test_create_mutants_returns_error_for_module_without_file():
    module = types.ModuleType("no_file")
    module.__file__ = None
    mutants, error = create_mutants(module, max_mutants=3)
    assert mutants == []
    assert error is not None


def test_create_mutants_returns_error_when_file_missing(tmp_path):
    module = types.ModuleType("missing_file")
    module.__file__ = str(tmp_path / "not_there.py")
    mutants, error = create_mutants(module, max_mutants=3)
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


def test_strip_redundant_pass_statements_removes_pass_when_other_stmts_exist():
    code = (
        "def test_x():\n"
        "    # Arrange\n"
        "    var = 1\n"
        "    # Act\n"
        "    pass\n"
        "    pass\n"
        "    assert var == 1\n"
    )
    cleaned = strip_redundant_pass_statements(code)
    assert "pass" not in cleaned
    assert "# Arrange" in cleaned
    assert "assert var == 1" in cleaned
    ast.parse(cleaned)


def test_strip_redundant_pass_statements_keeps_pass_in_otherwise_empty_block():
    code = (
        "def test_x():\n"
        "    try:\n"
        "        var = 1\n"
        "    except Exception:\n"
        "        pass\n"
        "    assert var == 1\n"
    )
    cleaned = strip_redundant_pass_statements(code)
    assert "except Exception:\n        pass" in cleaned
    ast.parse(cleaned)


def test_strip_redundant_pass_statements_keeps_pass_in_empty_function():
    code = "def test_x():\n    pass\n"
    cleaned = strip_redundant_pass_statements(code)
    assert cleaned.strip() == "def test_x():\n    pass"


def test_build_filtered_test_strips_redundant_pass():
    refined = "def test_x():\n    assert (\n        a == 1\n    )\n    assert b == 2\n"
    tree = ast.parse(refined)
    filtered = _build_filtered_test(refined, tree, [0])
    # The removed assert is replaced by pass during intermediate build, but since
    # assert b == 2 remains, redundant pass is stripped.
    assert "pass" not in filtered
    assert "assert b == 2" in filtered


def test_build_filtered_test_keeps_pass_if_body_would_be_empty():
    refined = "def test_x():\n    assert a == 1\n"
    tree = ast.parse(refined)
    filtered = _build_filtered_test(refined, tree, [0])
    assert "pass" in filtered


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
        "pynguin.refinement.mutation_analyzer.killed_set",
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
        "pynguin.refinement.mutation_analyzer.create_mutants",
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
        "pynguin.refinement.mutation_analyzer.create_mutants",
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
        "pynguin.refinement.mutation_analyzer.create_mutants",
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
        "pynguin.refinement.mutation_analyzer.create_mutants",
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
    assert "pass" not in filtered
    assert "assert a == 1" in filtered
    assert "assert b == 2" not in filtered
    assert stats["assertions_removed"] == 1
    assert stats["assertions_kept"] == 0
    assert stats["avg_per_test_contribution"] == 0.0


def test_get_surviving_mutants(monkeypatch):
    module = types.ModuleType("module_0")
    module.__file__ = "dummy.py"
    # Mock create_mutants to return a mock mutant
    monkeypatch.setattr(
        "pynguin.refinement.mutation_analyzer.create_mutants",
        lambda *_args, **_kwargs: ([("mutant_module", "mutations")], None),
    )
    # Mock killed_set to return empty (mutant survived)
    monkeypatch.setattr(
        "pynguin.refinement.mutation_analyzer.killed_set",
        lambda *_args, **_kwargs: set(),
    )
    survivors = get_surviving_mutants("def test_x(): pass", module)
    assert len(survivors) == 1
    assert survivors[0] == ("mutant_module", "mutations")


def test_get_surviving_mutants_excludes_failed_builds(monkeypatch):
    # Regression: mutants that failed to build (module is None) are skipped by
    # killed_set and must not be reported as survivors.
    module = types.ModuleType("module_0")
    module.__file__ = "dummy.py"
    monkeypatch.setattr(
        "pynguin.refinement.mutation_analyzer.create_mutants",
        lambda *_args, **_kwargs: (
            [(None, "mutations"), ("mutant_module", "mutations")],
            None,
        ),
    )
    monkeypatch.setattr(
        "pynguin.refinement.mutation_analyzer.killed_set",
        lambda *_args, **_kwargs: set(),
    )
    survivors = get_surviving_mutants("def test_x(): pass", module)
    assert survivors == [("mutant_module", "mutations")]


def test_evaluate_refined_suite_mutations_empty_or_none():
    res = evaluate_refined_suite_mutations("", [], None)
    assert res["post_refinement_mutation_score"] is None
    assert res["post_refinement_killed_mutants"] == 0

    module = types.ModuleType("test_mod")
    res2 = evaluate_refined_suite_mutations("", [], module)
    assert res2["post_refinement_mutation_score"] is None


def test_evaluate_refined_suite_mutations_creation_failure(monkeypatch):
    module = types.ModuleType("test_mod")
    monkeypatch.setattr(
        "pynguin.refinement.mutation_analyzer.create_mutation_controller",
        lambda _m: (_ for _ in ()).throw(RuntimeError("AST error")),
    )
    res = evaluate_refined_suite_mutations("import test_mod", ["def test_1(): pass"], module)
    assert res["post_refinement_mutation_score"] is None
    assert res["post_refinement_checked_mutants"] == 0


def test_evaluate_refined_suite_mutations_zero_mutants(monkeypatch):
    class _MockController:
        def mutant_count(self):
            return 0

    module = types.ModuleType("test_mod")
    monkeypatch.setattr(
        "pynguin.refinement.mutation_analyzer.create_mutation_controller",
        lambda _m: _MockController(),
    )
    res = evaluate_refined_suite_mutations("import test_mod", ["def test_1(): pass"], module)
    assert res["post_refinement_mutation_score"] == 1.0
    assert res["post_refinement_created_mutants"] == 0


def _mock_controller(monkeypatch, *mutants):
    class _MockController:
        def mutant_count(self):
            return len(mutants)

        def create_mutants(self):
            for mutant in mutants:
                yield mutant, []

    monkeypatch.setattr(
        "pynguin.refinement.mutation_analyzer.create_mutation_controller",
        lambda _m: _MockController(),
    )


def _mock_execute_test(monkeypatch, outcomes):
    """Make ``execute_test`` return the given outcomes, baseline runs first."""
    remaining = list(outcomes)

    def _execute(_source, _mod):
        return remaining.pop(0)

    monkeypatch.setattr("pynguin.refinement.mutation_analyzer.execute_test", _execute)


_PASSED = TestExecution("test_1", None, "Test passed.")
_FAILED = TestExecution("test_1", AssertionError(), "AssertionError")


def test_evaluate_refined_suite_mutations_happy_path(monkeypatch):
    module = types.ModuleType("test_mod")
    _mock_controller(monkeypatch, types.ModuleType("test_mod"), types.ModuleType("test_mod"))
    # Baseline passes, first mutant killed, second mutant survives
    _mock_execute_test(monkeypatch, [_PASSED, _FAILED, _PASSED])

    res = evaluate_refined_suite_mutations("import test_mod", ["def test_1(): pass"], module)
    assert res["post_refinement_mutation_score"] == 0.5
    assert res["post_refinement_killed_mutants"] == 1
    assert res["post_refinement_checked_mutants"] == 2
    assert res["post_refinement_timed_out_mutants"] == 0


def test_evaluate_refined_suite_mutations_timeout(monkeypatch):
    module = types.ModuleType("test_mod")
    _mock_controller(monkeypatch, types.ModuleType("test_mod"))
    timed_out = TestExecution(
        "test_1", TestExecutionTimeoutError(), "TimeoutError: timed out", timed_out=True
    )
    _mock_execute_test(monkeypatch, [_PASSED, timed_out])

    res = evaluate_refined_suite_mutations("import test_mod", ["def test_1(): pass"], module)
    assert res["post_refinement_mutation_score"] is None  # all checked mutants timed out
    assert res["post_refinement_killed_mutants"] == 0
    assert res["post_refinement_checked_mutants"] == 1
    assert res["post_refinement_timed_out_mutants"] == 1


def test_evaluate_refined_suite_mutations_kills_on_different_exception(monkeypatch):
    module = types.ModuleType("test_mod")
    _mock_controller(monkeypatch, types.ModuleType("test_mod"), types.ModuleType("test_mod"))
    # An (xfail) test raising ValueError on the original: the same exception on a
    # mutant kills nothing, another exception type kills it.
    _mock_execute_test(
        monkeypatch,
        [
            TestExecution("test_1", ValueError("pos"), "Exception"),
            TestExecution("test_1", ValueError("other message"), "Exception"),
            TestExecution("test_1", TypeError("nonpos"), "Exception"),
        ],
    )

    res = evaluate_refined_suite_mutations("import test_mod", ["def test_1(): pass"], module)
    assert res["post_refinement_killed_mutants"] == 1
    assert res["post_refinement_checked_mutants"] == 2
    assert res["post_refinement_mutation_score"] == 0.5


def test_evaluate_refined_suite_mutations_xfail_test_kills_mutants(tmp_path, monkeypatch):
    package = tmp_path / "xfail_pkg"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "exc.py").write_text(
        "def f(x):\n"
        "    if x > 0:\n"
        "        raise ValueError('pos')\n"
        "    raise TypeError('nonpos')\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    module = importlib.import_module("xfail_pkg.exc")
    preamble = "import pytest\nimport xfail_pkg.exc as module_0\n"
    xfail_test = "@pytest.mark.xfail(strict=True)\ndef test_case_0():\n    module_0.f(1)\n"
    raises_test = "def test_case_0():\n    with pytest.raises(ValueError):\n        module_0.f(1)\n"

    xfail_res = evaluate_refined_suite_mutations(preamble, [xfail_test], module, maximum_time=-1)
    raises_res = evaluate_refined_suite_mutations(preamble, [raises_test], module, maximum_time=-1)
    assert xfail_res["post_refinement_killed_mutants"] > 0
    assert xfail_res == raises_res


def test_evaluate_refined_suite_mutations_drops_mutant_interrupted_by_budget(monkeypatch):
    module = types.ModuleType("test_mod")
    _mock_controller(monkeypatch, types.ModuleType("test_mod"))
    # Baseline for both tests; the mutant survives the first test, then the budget
    # runs out before the second test (which would kill it) is run.
    _mock_execute_test(monkeypatch, [_PASSED, _PASSED, _PASSED])
    clock = iter([0.0, 0.0, 10.0])
    monkeypatch.setattr(
        "pynguin.refinement.mutation_analyzer.time.monotonic", lambda: next(clock, 10.0)
    )

    res = evaluate_refined_suite_mutations(
        "import test_mod",
        ["def test_1(): pass", "def test_2(): pass"],
        module,
        maximum_time=1,
    )
    assert res["post_refinement_checked_mutants"] == 0
    assert res["post_refinement_killed_mutants"] == 0
    assert res["post_refinement_mutation_score"] is None
    assert res["post_refinement_created_mutants"] == 1


def _mutations_on_line(line_number: int):
    node = ast.Constant(value=1)
    node.lineno = line_number
    return [types.SimpleNamespace(node=node)]


def test_rank_mutations_one_per_line_then_remaining_then_uncovered():
    # Lines 10 (2 mutations), 20 (2 mutations), 30 and 99 uncovered.
    lines = [10, 10, 20, 20, 30, 99]
    all_mutations = [_mutations_on_line(line) for line in lines]
    assert rank_mutations(all_mutations, {10, 20}) == [0, 2, 1, 3, 4, 5]


def test_rank_mutations_without_line_counts_as_uncovered():
    all_mutations = [[types.SimpleNamespace(node=ast.Add())], _mutations_on_line(5)]
    assert rank_mutations(all_mutations, {5}) == [1, 0]


def test_rank_mutations_no_coverage_returns_ast_order():
    all_mutations = [_mutations_on_line(1), _mutations_on_line(2)]
    assert rank_mutations(all_mutations, None) == [0, 1]
    assert rank_mutations(all_mutations, set()) == [0, 1]


def test_create_mutants_with_covered_lines(tmp_path):
    # Module with multiple lines and functions
    source = "def f1(x):\n    return x + 1\n\ndef f2(x):\n    return x + 10\n"
    mod_file = tmp_path / "two_funcs.py"
    mod_file.write_text(source, encoding="utf-8")
    spec = importlib.util.spec_from_file_location("two_funcs", mod_file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    # Covered line 5 (f2)
    mutants, error = create_mutants(module, max_mutants=1, covered_lines={5})
    assert error is None
    assert len(mutants) == 1
    # The selected mutant must be on line 5
    assert mutants[0][1][0].node.lineno == 5


def test_create_mutants_with_covered_lines_builds_only_selected(tmp_path, monkeypatch):
    source = "def f1(x):\n    return x + 1 + 2 + 3\n\ndef f2(x):\n    return x + 10\n"
    mod_file = tmp_path / "lazy_funcs.py"
    mod_file.write_text(source, encoding="utf-8")
    spec = importlib.util.spec_from_file_location("lazy_funcs", mod_file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    built = []
    original = MutationController.create_mutant

    def _counting_create_mutant(self, mutant_ast):
        built.append(mutant_ast)
        return original(self, mutant_ast)

    monkeypatch.setattr(MutationController, "create_mutant", _counting_create_mutant)
    mutants, error = create_mutants(module, max_mutants=2, covered_lines={5})
    assert error is None
    assert len(mutants) == 2
    assert len(built) == 2
    assert mutants[0][1][0].node.lineno == 5


def test_create_mutants_with_covered_lines_replaces_unbuildable(tmp_path, monkeypatch):
    source = "def f1(x):\n    return x + 1\n\ndef f2(x):\n    return x + 10\n"
    mod_file = tmp_path / "flaky_funcs.py"
    mod_file.write_text(source, encoding="utf-8")
    spec = importlib.util.spec_from_file_location("flaky_funcs", mod_file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    original = MutationController.create_mutant
    calls = []

    def _fail_first(self, mutant_ast):
        calls.append(mutant_ast)
        if len(calls) == 1:
            raise ValueError("boom")
        return original(self, mutant_ast)

    monkeypatch.setattr(MutationController, "create_mutant", _fail_first)
    mutants, error = create_mutants(module, max_mutants=1, covered_lines={5})
    assert error is None
    assert len(mutants) == 1
    assert len(calls) == 2


def test_filter_vacuous_assertions_preserves_late_function_assertion(tmp_path):
    """Integration test for Issue #326.

    A module where function A has many mutants, and function B has mutants further down.
    A test exercising function B must not have its valid assertion stripped.
    """
    source = (
        "def f1(x):\n"
        "    a = x + 1\n"
        "    b = a + 2\n"
        "    c = b + 3\n"
        "    d = c + 4\n"
        "    e = d + 5\n"
        "    f = e + 6\n"
        "    return f\n"
        "\n"
        "def f2(x):\n"
        "    return x + 100\n"
    )
    mod_file = tmp_path / "issue326_mod.py"
    mod_file.write_text(source, encoding="utf-8")
    spec = importlib.util.spec_from_file_location("issue326_mod", mod_file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    original_test = "import issue326_mod\ndef test_f2():\n    val = issue326_mod.f2(0)\n"
    # Refined test adds an assertion verifying f2(0) == 100
    refined_test = (
        "import issue326_mod\ndef test_f2():\n    val = issue326_mod.f2(0)\n    assert val == 100\n"
    )

    filtered, stats = filter_vacuous_assertions(
        original_test=original_test,
        refined_test=refined_test,
        module_under_test=module,
        max_mutants=5,  # Fewer than f1's mutants!
    )

    # The assertion should NOT be removed!
    assert "assert val == 100" in filtered
    assert stats["assertions_kept"] == 1
    assert stats["assertions_removed"] == 0
