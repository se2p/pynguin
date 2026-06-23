#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Tests for the in-process test execution validator (validator.py)."""

from __future__ import annotations

import math
import sys
import types

from pynguin.refinement.validator import _ensure_module_package_on_path, run_test


def test_run_test_passing():
    code = "def test_ok():\n    assert math.sqrt(4) == 2\n"
    passed, message = run_test(code, math)
    assert passed is True
    assert message == "Test passed."


def test_run_test_failing_assertion():
    code = "def test_bad():\n    assert math.sqrt(4) == 3\n"
    passed, message = run_test(code, math)
    assert passed is False
    assert "AssertionError" in message


def test_run_test_runtime_exception():
    code = "def test_err():\n    undefined_symbol_xyz\n"
    passed, message = run_test(code, math)
    assert passed is False
    assert "Exception" in message


def test_run_test_missing_function_name():
    passed, message = run_test("x = 1\n", math)
    assert passed is False
    assert "Could not find function name" in message


def test_run_test_multi_statement_passing():
    code = "def test_ok():\n    value = math.floor(1.5)\n    assert value == 1\n"
    passed, message = run_test(code, math)
    assert passed is True
    assert message == "Test passed."


def test_ensure_module_package_on_path_without_file_returns_none():
    class _FakeModule:
        __name__ = "fake_module"

    assert _ensure_module_package_on_path(_FakeModule()) is None


def test_ensure_module_package_on_path_adds_package_root(tmp_path):
    package_dir = tmp_path / "pkg"
    package_dir.mkdir()
    (package_dir / "__init__.py").write_text("", encoding="utf-8")
    (package_dir / "mod.py").write_text("value = 1\n", encoding="utf-8")

    fake_module = types.ModuleType("pkg.mod")
    fake_module.__file__ = str(package_dir / "mod.py")

    root = str(tmp_path)
    added = None
    try:
        assert root not in sys.path
        added = _ensure_module_package_on_path(fake_module)
        assert added == root
        assert root in sys.path
    finally:
        if added in sys.path:
            sys.path.remove(added)
