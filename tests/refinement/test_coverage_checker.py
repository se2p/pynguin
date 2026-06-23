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

import pytest

from pynguin.refinement.coverage_checker import (
    _executable_lines,  # noqa: PLC2701
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
