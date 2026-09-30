#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Tests for the refinement entry point (refiner.py)."""

from __future__ import annotations

import ast
import types

import pytest

import pynguin.configuration as config
from pynguin.refinement import refiner as refiner_module
from pynguin.refinement.refiner import (
    _attach_usage,  # noqa: PLC2701
    _extract_function_text,  # noqa: PLC2701
    _failure_stats,  # noqa: PLC2701
    _finalize_refined_suite,  # noqa: PLC2701
    _hoist_local_imports,  # noqa: PLC2701
    _is_test_function,  # noqa: PLC2701
    _load_test_functions,  # noqa: PLC2701
    _MutationAccumulator,  # noqa: PLC2701
    _new_stats,  # noqa: PLC2701
    _process_one_test,  # noqa: PLC2701
    _sanitize_test,  # noqa: PLC2701
    _TestOutcome,  # noqa: PLC2701
    _track_statistics,  # noqa: PLC2701
    refine_generated_tests,
)
from pynguin.utils.statistics.runtimevariable import RuntimeVariable


def test_extract_function_text_strips_imports():
    code = "import module_0\n\ndef test_x():\n    assert True\n"
    extracted = _extract_function_text(code)
    assert extracted.startswith("def test_x():")
    assert "import module_0" not in extracted


def test_extract_function_text_keeps_decorator():
    code = "@some.decorator\ndef test_x():\n    assert True\n"
    extracted = _extract_function_text(code)
    assert extracted.startswith("@some.decorator")


def test_extract_function_text_preserves_aaa_comments():
    code = (
        "import module_0\n\n"
        "def test_x():\n"
        "    # Arrange\n"
        "    x = 1\n"
        "    # Act\n"
        "    y = module_0.f(x)\n"
        "    # Assert\n"
        "    assert y\n"
    )
    extracted = _extract_function_text(code)
    assert "# Arrange" in extracted
    assert "# Act" in extracted
    assert "# Assert" in extracted


def test_extract_function_text_syntax_error_fallback():
    code = "def broken(:\n    pass\n"
    # Falls back to the line-based scan and still returns from the def.
    assert _extract_function_text(code).startswith("def broken(")


def test_extract_function_text_returns_original_when_no_def_or_decorator():
    code = "x = 1\ny = 2\n"
    assert _extract_function_text(code) == code


def test_failure_stats_with_error_field():
    stats = _failure_stats(error="boom", wall_time=1.25)
    assert stats["error"] == "boom"
    assert stats["wall_time_seconds"] == 1.25


def test_mutation_accumulator_add_and_finalize():
    stats = _new_stats()
    acc = _MutationAccumulator()
    acc.add(
        stats,
        {
            "inferred_assertions": 2,
            "assertions_removed": 1,
            "assertions_kept": 1,
            "mutants_generated": 5,
            "mutants_killed_total": 3,
            "suite_baseline_size": 7,
            "per_test_contributions": {"a": 2, "b": 4},
            "suite_level_contributions": {"x": 6},
        },
    )
    acc.finalize(stats)
    assert stats["mutation_inferred_total"] == 2
    assert stats["mutation_removed_total"] == 1
    assert stats["mutation_kept_total"] == 1
    assert stats["mutation_mutants_generated_total"] == 5
    assert stats["mutation_mutants_killed_total"] == 3
    assert stats["mutation_suite_baseline_size_total"] == 7
    assert stats["mutation_per_test_contribution_mean"] == 3.0
    assert stats["mutation_suite_contribution_mean"] == 6.0


def test_process_one_test_success(monkeypatch):
    func = ast.parse("def test_case_0():\n    assert True\n").body[0]

    class _FakeRefiner:
        def process_test_end_to_end(self, **_kwargs):
            return {
                "success": True,
                "final_code": "def test_case_renamed():\n    assert True\n",
                "iterations": 2,
                "mutation_stats": {"inferred_assertions": 1},
            }

    monkeypatch.setattr(
        refiner_module,
        "compute_metrics",
        lambda code: {"aggregate": 0.2 if "test_case_0" in code else 0.8},
    )

    outcome = _process_one_test(
        refiner=_FakeRefiner(),
        preamble="",
        func=func,
        max_repair_iterations=3,
    )

    assert outcome.processed is True
    assert outcome.refined is True
    assert outcome.failed is False
    assert outcome.iterations == 2
    assert outcome.readability_original == 0.2
    assert outcome.readability_refined == 0.8
    assert outcome.mutation_stats["inferred_assertions"] == 1


def test_process_one_test_failed_result(monkeypatch):
    func = ast.parse("def test_case_0():\n    assert True\n").body[0]

    class _FakeRefiner:
        def process_test_end_to_end(self, **_kwargs):
            return {"success": False, "error": "invalid test"}

    monkeypatch.setattr(refiner_module, "compute_metrics", lambda _code: {"aggregate": 0.5})

    outcome = _process_one_test(
        refiner=_FakeRefiner(),
        preamble="",
        func=func,
        max_repair_iterations=1,
    )

    assert outcome.processed is True
    assert outcome.refined is False
    assert outcome.failed is True


def test_process_one_test_exception_path(monkeypatch):
    func = ast.parse("def test_case_0():\n    assert True\n").body[0]

    class _FakeRefiner:
        def process_test_end_to_end(self, **_kwargs):
            raise RuntimeError("boom")

    monkeypatch.setattr(refiner_module, "compute_metrics", lambda _code: {"aggregate": 0.5})

    outcome = _process_one_test(
        refiner=_FakeRefiner(),
        preamble="",
        func=func,
        max_repair_iterations=1,
    )

    assert outcome.failed is True
    assert outcome.processed is False


def test_attach_usage_handles_usage_exception():
    stats = _new_stats()

    class _FailingLLMClient:
        def get_usage(self):
            raise RuntimeError("no usage")

    fake_refiner = types.SimpleNamespace(llm_client=_FailingLLMClient())
    _attach_usage(stats, fake_refiner, start_wall=0.0)
    assert stats["llm_calls"] == 0
    assert stats["llm_input_tokens"] == 0
    assert stats["llm_output_tokens"] == 0


def test_track_statistics_emits_all_runtime_variables(monkeypatch):
    calls: list[tuple[RuntimeVariable, int | float]] = []

    def _record(variable, value):
        calls.append((variable, value))

    monkeypatch.setattr(refiner_module.stat, "track_output_variable", _record)
    _track_statistics({
        "tests_processed": 4,
        "tests_refined": 3,
        "repair_iterations": 5,
        "failed_tests": 1,
        "readability_original": 0.3,
        "readability_refined": 0.7,
        "readability_delta": 0.4,
        "llm_calls": 6,
        "llm_input_tokens": 70,
        "llm_output_tokens": 10,
        "wall_time_seconds": 2.5,
        "mutation_inferred_total": 8,
        "mutation_removed_total": 2,
        "mutation_kept_total": 6,
        "mutation_mutants_generated_total": 12,
        "mutation_mutants_killed_total": 4,
        "mutation_suite_baseline_size_total": 9,
        "mutation_per_test_contribution_mean": 1.5,
        "mutation_suite_contribution_mean": 2.0,
    })

    emitted = {variable for variable, _ in calls}
    assert len(calls) == 19
    assert RuntimeVariable.TestsProcessed in emitted
    assert RuntimeVariable.RefinementSuiteContributionMean in emitted


def test_refine_generated_tests_happy_path_with_mocked_pipeline(tmp_path, monkeypatch):
    test_file = tmp_path / "test_mod.py"
    test_file.write_text("def test_case_0():\n    assert True\n", encoding="utf-8")

    fake_module = types.ModuleType("fake_module")
    func = ast.parse("def test_case_0():\n    assert True\n").body[0]

    class _FakeClient:
        def reset_usage(self):
            return None

        def get_usage(self):
            return {
                "calls": 2,
                "input_tokens": 10,
                "output_tokens": 4,
                "time_seconds": 0.5,
            }

    class _FakeRefiner:
        def __init__(self, **_kwargs):
            self.llm_client = _FakeClient()

    def _fake_process(*_args, **_kwargs):
        return _TestOutcome(
            func_text="def test_case_0():\n    assert True\n",
            processed=True,
            refined=True,
            iterations=2,
            readability_original=0.2,
            readability_refined=0.8,
            mutation_stats={
                "inferred_assertions": 1,
                "assertions_removed": 0,
                "assertions_kept": 1,
                "mutants_generated": 3,
                "mutants_killed_total": 2,
                "suite_baseline_size": 1,
                "per_test_contributions": {"test_case_0": 2},
                "suite_level_contributions": {"test_case_0": 2},
            },
        )

    monkeypatch.setattr(refiner_module, "_load_test_functions", lambda _p: ("", [func]))
    monkeypatch.setattr(refiner_module, "_import_module_under_test", lambda _m: fake_module)
    monkeypatch.setattr(refiner_module, "TestRefiner", _FakeRefiner)
    monkeypatch.setattr(refiner_module, "_process_one_test", _fake_process)
    # The fake module cannot actually execute the tests; treat every test as
    # green so the suite-finalization step keeps them (it validates via run_test).
    monkeypatch.setattr(refiner_module, "run_test", lambda *_a, **_k: (True, "Test passed."))
    # This test exercises the per-test path (mocking _process_one_test), so pin the
    # granularity to PER_TEST rather than the new COMBINED default.
    monkeypatch.setattr(
        config.configuration.llm_refinement,
        "refinement_granularity",
        config.RefinementGranularity.PER_TEST,
    )

    stats = refine_generated_tests(
        test_file_path=test_file,
        module_name="fake_module",
        max_repair_iterations=3,
        max_tests=1,
    )

    assert stats["tests_processed"] == 1
    assert stats["tests_refined"] == 1
    assert stats["repair_iterations"] == 2
    assert stats["readability_delta"] == pytest.approx(0.6)
    assert stats["llm_calls"] == 2
    assert stats["mutation_inferred_total"] == 1


_EXPORTED_FILE = (
    "import sys\n"
    "import ftfy.fixes\n"
    "fixes_ = sys.modules['ftfy.fixes']\n"
    "from ftfy.fixes import fix_text\n\n\n"
    "@pytest.fixture(autouse=True)\n"
    "def _pynguin_seed_random():\n"
    "    yield\n\n\n"
    "def test_0():\n"
    "    assert fixes_ is not None\n\n\n"
    "def test_1():\n"
    "    assert fix_text('x') == 'x'\n"
)


def test_is_test_function_identifies_only_test_defs():
    tree = ast.parse(_EXPORTED_FILE)
    names = {node.name for node in tree.body if _is_test_function(node)}
    assert names == {"test_0", "test_1"}


def test_load_test_functions_preserves_module_alias_in_preamble(tmp_path):
    test_file = tmp_path / "test_fixes.py"
    test_file.write_text(_EXPORTED_FILE, encoding="utf-8")

    preamble, test_functions = _load_test_functions(test_file)

    # The `<mod>_ = sys.modules[...]` alias must survive in the preamble so that
    # tests referencing `fixes_` still resolve (regression for issue #304).
    assert "fixes_ = sys.modules['ftfy.fixes']" in preamble
    assert "import sys" in preamble
    assert "from ftfy.fixes import fix_text" in preamble
    # The autouse reseed fixture is preamble, not a test to refine.
    assert "_pynguin_seed_random" in preamble
    assert [func.name for func in test_functions] == ["test_0", "test_1"]


def test_load_test_functions_empty_preamble_when_only_tests(tmp_path):
    test_file = tmp_path / "test_only.py"
    test_file.write_text("def test_0():\n    assert True\n", encoding="utf-8")

    preamble, test_functions = _load_test_functions(test_file)

    assert not preamble
    assert [func.name for func in test_functions] == ["test_0"]


def test_refined_file_keeps_module_alias(tmp_path, monkeypatch):
    """End-to-end: the written *_refined.py preserves the full preamble (issue #304)."""
    test_file = tmp_path / "test_fixes.py"
    test_file.write_text(_EXPORTED_FILE, encoding="utf-8")

    fake_module = types.ModuleType("fake_module")

    class _FakeClient:
        def reset_usage(self):
            return None

        def get_usage(self):
            return {"calls": 1, "input_tokens": 1, "output_tokens": 1}

    class _FakeRefiner:
        def __init__(self, **_kwargs):
            self.llm_client = _FakeClient()

    def _fake_process(_refiner, _preamble, func, _max_iterations):
        # Echo the original test body back as the "refined" text.
        return _TestOutcome(
            func_text=ast.unparse(func),
            processed=True,
            refined=True,
            iterations=1,
            readability_original=0.1,
            readability_refined=0.2,
        )

    monkeypatch.setattr(refiner_module, "_import_module_under_test", lambda _m: fake_module)
    monkeypatch.setattr(refiner_module, "TestRefiner", _FakeRefiner)
    monkeypatch.setattr(refiner_module, "_process_one_test", _fake_process)
    # The fake module cannot actually execute the tests; treat every test as
    # green so the suite-finalization step keeps them (it validates via run_test).
    monkeypatch.setattr(refiner_module, "run_test", lambda *_a, **_k: (True, "Test passed."))
    monkeypatch.setattr(
        config.configuration.llm_refinement,
        "refinement_granularity",
        config.RefinementGranularity.PER_TEST,
    )

    refine_generated_tests(
        test_file_path=test_file,
        module_name="fake_module",
        max_tests=None,
    )

    refined = (tmp_path / "test_fixes_refined.py").read_text(encoding="utf-8")
    assert "fixes_ = sys.modules['ftfy.fixes']" in refined
    assert "import sys" in refined
    assert "_pynguin_seed_random" in refined
    assert "def test_0():" in refined
    assert "def test_1():" in refined


def test_refine_generated_tests_exception_tracks_error(tmp_path, monkeypatch):
    test_file = tmp_path / "test_mod.py"
    test_file.write_text("def test_case_0():\n    assert True\n", encoding="utf-8")

    def _raise_bad_parse(_p):
        raise RuntimeError("bad parse")

    monkeypatch.setattr(refiner_module, "_load_test_functions", _raise_bad_parse)
    recorded: list[dict[str, object]] = []
    monkeypatch.setattr(refiner_module, "_track_statistics", lambda s: recorded.append(s.copy()))

    stats = refine_generated_tests(
        test_file_path=test_file,
        module_name="json",
    )

    assert "error" in stats
    assert "bad parse" in stats["error"]
    assert recorded
    assert recorded[0]["tests_processed"] == 0


def test_refine_returns_empty_stats_for_unimportable_module(tmp_path):
    test_file = tmp_path / "test_mod.py"
    test_file.write_text("def test_case_0():\n    assert True\n", encoding="utf-8")

    stats = refine_generated_tests(
        test_file_path=test_file,
        module_name="totally_nonexistent_module_xyz",
    )
    assert stats["tests_processed"] == 0
    assert stats["tests_refined"] == 0
    assert "error" not in stats


def test_refine_returns_error_for_missing_file(tmp_path):
    missing = tmp_path / "does_not_exist.py"
    stats = refine_generated_tests(
        test_file_path=missing,
        module_name="json",
    )
    assert stats["tests_processed"] == 0
    assert "error" in stats


# ===================================================================
# out-of-scope import hoisting / suite finalization
# ===================================================================


def test_hoist_local_imports_promotes_cross_test_import():
    """An import used by one test but declared inside another is hoisted."""
    preamble = "import sys\nlog_ = sys.modules['pytutils.log']\n"
    tests = [
        "def test_8():\n    from unittest.mock import MagicMock\n    m = MagicMock()\n",
        "def test_11():\n    logger = MagicMock()\n    assert logger is not None\n",
    ]

    new_preamble = _hoist_local_imports(preamble, tests)

    assert "from unittest.mock import MagicMock" in new_preamble
    # The original preamble lines are preserved.
    assert "log_ = sys.modules['pytutils.log']" in new_preamble


def test_hoist_local_imports_no_duplicate_when_already_module_scope():
    """An import already at module scope is not duplicated."""
    preamble = "from unittest.mock import MagicMock\n"
    tests = ["def test_0():\n    m = MagicMock()\n    assert m is not None\n"]

    new_preamble = _hoist_local_imports(preamble, tests)

    assert new_preamble.count("from unittest.mock import MagicMock") == 1


def test_finalize_refined_suite_hoists_and_keeps_valid_tests(monkeypatch):
    """Finalization hoists imports and keeps executable tests."""
    preamble = "import sys\n"
    tests = [
        "def test_0():\n    from unittest.mock import MagicMock\n"
        "    assert MagicMock() is not None\n",
        "def test_1():\n    logger = MagicMock()\n    assert logger is not None\n",
    ]
    module = types.ModuleType("dummy")

    monkeypatch.setattr(refiner_module, "run_test", lambda *_a, **_k: (True, "ok"))

    new_preamble, kept = _finalize_refined_suite(preamble, tests, module)

    assert "from unittest.mock import MagicMock" in new_preamble
    assert len(kept) == 2


def test_sanitize_test_drops_non_executable_test(monkeypatch):
    """A test that fails to execute (e.g. NameError) is dropped, never exported."""
    module = types.ModuleType("dummy")
    monkeypatch.setattr(
        refiner_module, "run_test", lambda *_a, **_k: (False, "NameError: name 'x' is not defined")
    )

    result = _sanitize_test("import sys\n", "def test_0():\n    assert x == 1\n", module)

    assert result is None


def test_sanitize_test_strips_stale_xfail_on_xpass(monkeypatch):
    """A now-passing xfail(strict) test has its marker stripped instead of failing."""
    module = types.ModuleType("dummy")
    calls = {"n": 0}

    def fake_run_test(_code, _module):
        calls["n"] += 1
        # First call: the xfail-marked test XPASSes (a failure); second call
        # (after the marker is stripped): it passes cleanly.
        if calls["n"] == 1:
            return False, "XPASS(strict): test is marked xfail(strict=True) but passed."
        return True, "Test passed."

    monkeypatch.setattr(refiner_module, "run_test", fake_run_test)

    func = "@pytest.mark.xfail(strict=True)\ndef test_0():\n    assert True\n"
    result = _sanitize_test("import pytest\n", func, module)

    assert result is not None
    assert "xfail" not in result
