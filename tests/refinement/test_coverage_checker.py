#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Tests for the coverage preservation checker (coverage_checker.py)."""

from __future__ import annotations

import importlib.util
import types
from pathlib import Path

import pytest

import pynguin.configuration as config
from pynguin.refinement.coverage_checker import (
    CoverageResult,
    _executable_lines,  # noqa: PLC2701
    _find_test_function_name,  # noqa: PLC2701
    _load_sut_source,  # noqa: PLC2701
    _measure_coverage_pynguin,  # noqa: PLC2701
    _measure_coverage_settrace,  # noqa: PLC2701
    check_coverage_preservation,
)

_SUT_SOURCE = """\
def add(a, b):
    result = a + b
    return result


def unused(x):
    return x * 2
"""


@pytest.fixture
def sut_module(tmp_path):
    path = tmp_path / "cov_sut_mod.py"
    path.write_text(_SUT_SOURCE, encoding="utf-8")
    spec = importlib.util.spec_from_file_location("cov_sut_mod", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_executable_lines_excludes_def_and_import():
    source = "import os\nx = 1\ndef f():\n    return x\n"
    assert _executable_lines(source) == {2, 4}


def test_executable_lines_syntax_error_returns_empty():
    assert _executable_lines("def broken(:\n") == set()


def test_settrace_measures_coverage(sut_module):
    code = "def test_x():\n    assert cov_sut_mod.add(1, 2) == 3\n"
    result = _measure_coverage_settrace(code, sut_module)
    assert result.error is None
    assert result.metric == "line"
    assert result.coverage_value > 0.0


def test_settrace_without_file_returns_error():
    module = types.ModuleType("no_file_module")
    result = _measure_coverage_settrace("def test_x():\n    pass\n", module)
    assert result.error is not None


def test_check_preservation_passes_for_equal_coverage(sut_module):
    code = "def test_x():\n    assert cov_sut_mod.add(1, 2) == 3\n"
    passed, details = check_coverage_preservation(code, code, sut_module)
    assert passed is True
    assert details["status"] == "passed"
    assert details["coverage_delta"] == pytest.approx(0.0)


def test_check_preservation_fails_when_coverage_drops(sut_module):
    original = (
        "def test_x():\n"
        "    assert cov_sut_mod.add(1, 2) == 3\n"
        "    assert cov_sut_mod.unused(2) == 4\n"
    )
    refined = "def test_x():\n    assert cov_sut_mod.add(1, 2) == 3\n"
    passed, details = check_coverage_preservation(original, refined, sut_module)
    assert passed is False
    assert details["status"] == "failed"


def test_check_preservation_skips_on_measurement_error():
    module = types.ModuleType("no_file_module")
    passed, details = check_coverage_preservation(
        "def test_x():\n    pass\n", "def test_x():\n    pass\n", module
    )
    # Measurement error -> treated as skipped (non-blocking) and passes.
    assert passed is True
    assert details["status"] == "skipped"


def test_find_test_function_name_returns_first_def():
    code = "\n\n# comment\ndef test_abc(x):\n    return x\n"
    assert _find_test_function_name(code) == "test_abc"


def test_find_test_function_name_returns_empty_when_missing():
    assert not _find_test_function_name("x = 1\ny = 2\n")


def test_load_sut_source_missing_file_returns_error(tmp_path):
    module = types.ModuleType("missing_mod")
    module.__file__ = str(tmp_path / "nope.py")
    path, source, error = _load_sut_source(module)
    assert path is None
    assert source is None
    assert "not found" in (error or "")


def test_load_sut_source_read_error(monkeypatch, tmp_path):
    module = types.ModuleType("read_fail_mod")
    fake_path = tmp_path / "x.py"
    fake_path.write_text("x = 1\n", encoding="utf-8")
    module.__file__ = str(fake_path)
    monkeypatch.setattr(
        Path,
        "read_text",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("boom")),
    )
    path, source, error = _load_sut_source(module)
    assert path is None
    assert source is None
    assert "Could not read SUT source" in (error or "")


def test_measure_coverage_settrace_returns_error_when_no_executable_lines(tmp_path):
    module = types.ModuleType("empty_mod")
    src = tmp_path / "empty_mod.py"
    src.write_text("import os\n", encoding="utf-8")
    module.__file__ = str(src)
    result = _measure_coverage_settrace("def test_x():\n    pass\n", module)
    assert result.error is not None
    assert result.metric == "line"


def test_check_preservation_uses_pynguin_measurement(monkeypatch):
    monkeypatch.setattr(
        "pynguin.refinement.coverage_checker._measure_coverage_pynguin",
        lambda code, *_args, **_kwargs: CoverageResult(
            coverage_value=0.8 if "original" in code else 0.9,
            metric="branch",
        ),
    )
    # In this path _measure_coverage_settrace must not be used.
    monkeypatch.setattr(
        "pynguin.refinement.coverage_checker._measure_coverage_settrace",
        lambda *_args, **_kwargs: CoverageResult(error="should not be called"),
    )

    subject_properties = types.SimpleNamespace(instrumentation_tracer=object())
    passed, details = check_coverage_preservation(
        original_test="# original\ndef test_x():\n    pass\n",
        refined_test="# refined\ndef test_x():\n    pass\n",
        module_under_test=types.ModuleType("m"),
        subject_properties=subject_properties,
    )

    assert passed is True
    assert details["metric"] == "branch"
    assert details["coverage_delta"] == pytest.approx(0.1)


def test_check_preservation_pynguin_path_fails_when_refined_drops(monkeypatch):
    monkeypatch.setattr(
        "pynguin.refinement.coverage_checker._measure_coverage_pynguin",
        lambda code, *_args, **_kwargs: CoverageResult(
            coverage_value=0.8 if "original" in code else 0.6,
            metric="branch",
        ),
    )
    subject_properties = types.SimpleNamespace(instrumentation_tracer=object())
    passed, details = check_coverage_preservation(
        original_test="# original\ndef test_x():\n    pass\n",
        refined_test="# refined\ndef test_x():\n    pass\n",
        module_under_test=types.ModuleType("m"),
        subject_properties=subject_properties,
    )
    assert passed is False
    assert details["status"] == "failed"


def test_measure_coverage_pynguin_uses_line_metric(monkeypatch):
    class _DummyTrace:
        def __init__(self):
            self.executed_code_objects: list[int] = []
            self.covered_line_ids: list[int] = []

    class _DummyCtx:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            return False

    class _DummyTracer:
        def __init__(self):
            self.tracer = types.SimpleNamespace(_current_thread_identifier=None)

        def init_trace(self):
            return None

        def temporarily_enable(self):
            return _DummyCtx()

        def get_trace(self):
            return _DummyTrace()

    module = types.ModuleType("dummy_cov_mod")
    module.identity = lambda x: x
    subject_properties = types.SimpleNamespace(instrumentation_tracer=_DummyTracer())

    monkeypatch.setattr(
        config.configuration.statistics_output,
        "coverage_metrics",
        [config.CoverageMetric.LINE],
    )
    monkeypatch.setattr(
        "pynguin.refinement.coverage_checker.compute_line_coverage",
        lambda *_args, **_kwargs: 0.55,
    )
    monkeypatch.setattr(
        "pynguin.refinement.coverage_checker.compute_branch_coverage",
        lambda *_args, **_kwargs: 0.11,
    )

    result = _measure_coverage_pynguin(
        "def test_x():\n    assert dummy_cov_mod.identity(1) == 1\n",
        module,
        subject_properties,
    )
    assert result.error is None
    assert result.metric == "line"
    assert result.coverage_value == pytest.approx(0.55)
