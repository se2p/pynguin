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
import threading
import time
import types

import pytest

import pynguin.configuration as config
from pynguin.refinement.validator import (
    TestExecutionTimeoutError,
    _ensure_module_package_on_path,  # noqa: PLC2701
    resolve_timeout,
    run_test,
    time_limit,
)


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


def test_run_test_times_out_on_runaway_test():
    code = "def test_hang():\n    while True:\n        pass\n"
    started = time.monotonic()
    passed, message = run_test(code, math, timeout=0.5)
    elapsed = time.monotonic() - started

    assert passed is False
    assert "TimeoutError" in message
    assert elapsed < 10, "the runaway test was not aborted by the time limit"


def test_run_test_timeout_is_not_swallowed_by_the_test_code():
    code = (
        "def test_hang():\n"
        "    try:\n"
        "        while True:\n"
        "            pass\n"
        "    except Exception:\n"
        "        pass\n"
    )
    passed, message = run_test(code, math, timeout=0.5)

    assert passed is False
    assert "TimeoutError" in message


def test_run_test_non_positive_timeout_disables_the_limit():
    code = "def test_ok():\n    assert math.sqrt(4) == 2\n"
    passed, message = run_test(code, math, timeout=0)
    assert passed is True
    assert message == "Test passed."


def test_run_test_timeout_defaults_to_configured_execution_timeout():
    config.configuration.stopping.maximum_test_execution_timeout = 1
    code = "def test_hang():\n    while True:\n        pass\n"
    passed, message = run_test(code, math)

    assert passed is False
    assert "TimeoutError" in message


def test_resolve_timeout_prefers_the_explicit_value():
    config.configuration.stopping.maximum_test_execution_timeout = 5
    assert resolve_timeout(0.25) == 0.25
    assert resolve_timeout(None) == 5


def test_time_limit_restores_the_previous_alarm_handler():
    import signal  # noqa: PLC0415

    before = signal.getsignal(signal.SIGALRM)
    with time_limit(30):
        pass
    assert signal.getsignal(signal.SIGALRM) is before


def test_time_limit_is_skipped_off_the_main_thread():
    outcome: list[str] = []

    def _run():
        try:
            with time_limit(0.25):
                outcome.append("entered")
        except (ValueError, TestExecutionTimeoutError) as error:  # pragma: no cover
            outcome.append(f"raised {type(error).__name__}")

    worker = threading.Thread(target=_run)
    worker.start()
    worker.join(timeout=10)

    assert outcome == ["entered"]


def test_time_limit_raises_on_expiry():
    with pytest.raises(TestExecutionTimeoutError), time_limit(0.25):
        time.sleep(5)


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
