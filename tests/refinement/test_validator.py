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
    _extract_target_function_name,  # noqa: PLC2701
    call_test_functions,
    collect_test_functions,
    execute_test,
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


def test_run_test_xfail_strict_body_raises_is_green():
    """An xfail(strict=True) test whose body raises is xfail -> pytest passes."""
    code = (
        "import pytest\n"
        "@pytest.mark.xfail(strict=True)\n"
        "def test_expected_failure():\n"
        "    raise TypeError('boom')\n"
    )
    passed, message = run_test(code, math)
    assert passed is True
    assert "xfail" in message


def test_run_test_xfail_strict_body_passes_is_xpass_failure():
    """An xfail(strict=True) test whose body no longer raises is XPASS(strict) -> failure.

    This is the regression from issue #305: refinement rewrites the body into
    ``pytest.raises`` (so it no longer raises out) but keeps the xfail marker.
    """
    code = (
        "import pytest\n"
        "@pytest.mark.xfail(strict=True)\n"
        "def test_was_expected_to_fail():\n"
        "    with pytest.raises(TypeError):\n"
        "        raise TypeError('boom')\n"
    )
    passed, message = run_test(code, math)
    assert passed is False
    assert "XPASS(strict)" in message


def test_run_test_xfail_non_strict_body_passes_is_green():
    """A non-strict xfail that passes is only a warning, so pytest still passes."""
    code = "import pytest\n@pytest.mark.xfail\ndef test_maybe_fails():\n    assert True\n"
    passed, _ = run_test(code, math)
    assert passed is True


def test_run_test_xfail_strict_timeout_is_still_failure():
    """A timeout is a hard failure regardless of the xfail marker."""
    code = (
        "import pytest\n"
        "@pytest.mark.xfail(strict=True)\n"
        "def test_hang():\n"
        "    while True:\n"
        "        pass\n"
    )
    passed, message = run_test(code, math, timeout=0.5)
    assert passed is False
    assert "TimeoutError" in message


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


_XFAIL_MODULE = (
    "import pytest\n\n"
    "@pytest.mark.xfail(strict=True)\n"
    "def test_strict():\n    raise ValueError\n\n"
    "@pytest.mark.xfail\n"
    "def test_lenient():\n    pass\n\n"
    "def helper():\n    pass\n\n"
    "def test_plain():\n    pass\n"
)


def test_collect_test_functions_reports_xfail_markers_in_order():
    assert collect_test_functions(_XFAIL_MODULE) == [
        ("test_strict", True, True),
        ("test_lenient", True, False),
        ("test_plain", False, False),
    ]


def test_collect_test_functions_unparseable_code():
    assert collect_test_functions("def broken(:") == []


def test_call_test_functions_runs_all_tests_and_honours_xfail():
    calls = []

    def raising():
        raise ValueError

    scope = {
        "test_strict": raising,
        "test_lenient": lambda: None,
        "test_plain": lambda: calls.append("plain"),
    }
    call_test_functions(scope, collect_test_functions(_XFAIL_MODULE))
    assert calls == ["plain"]


def test_call_test_functions_raises_on_strict_xpass():
    scope = {"test_x": lambda: None}
    with pytest.raises(AssertionError, match="XPASS"):
        call_test_functions(scope, [("test_x", True, True)])


def test_call_test_functions_propagates_regular_failure():
    def failing():
        raise ValueError("boom")

    with pytest.raises(ValueError, match="boom"):
        call_test_functions({"test_x": failing}, [("test_x", False, False)])


_PREAMBLE_WITH_DETERMINISTIC_SEED = (
    "import pytest\n"
    "import random as _pynguin_random\n"
    "import weakref as _pynguin_weakref\n"
    "_pynguin_orig_seed = getattr(\n"
    "    _pynguin_random.Random.seed, '__pynguin_orig__', _pynguin_random.Random.seed\n"
    ")\n"
    "_pynguin_tracked = _pynguin_weakref.WeakSet()\n"
    "def _pynguin_deterministic_seed(self, x=None):\n"
    "    if x is None:\n"
    "        x = 42\n"
    "    _pynguin_orig_seed(self, x)\n"
    "    _pynguin_tracked.add(self)\n"
    "_pynguin_deterministic_seed.__pynguin_patched__ = True\n"
    "_pynguin_deterministic_seed.__pynguin_orig__ = _pynguin_orig_seed\n"
    "_pynguin_deterministic_seed.__pynguin_instances__ = _pynguin_tracked\n"
    "_pynguin_random.Random.seed = _pynguin_deterministic_seed\n\n"
    "@pytest.fixture(autouse=True)\n"
    "def _pynguin_seed_random():\n"
    "    yield\n"
)


def test_extract_target_function_name_with_seed_preamble():
    code = f"{_PREAMBLE_WITH_DETERMINISTIC_SEED}\ndef test_case_0():\n    assert True\n"
    assert _extract_target_function_name(code) == "test_case_0"


def test_extract_target_function_name_multiple_tests():
    code = "def test_1():\n    pass\ndef helper():\n    pass\ndef test_2():\n    pass\n"
    assert _extract_target_function_name(code) == "test_2"


def test_extract_target_function_name_fallback_no_test_prefix():
    code = "def helper():\n    pass\n"
    assert _extract_target_function_name(code) == "helper"


def test_extract_target_function_name_syntax_error():
    code = "def _helper(:\ndef test_ok():\n    pass\n"
    assert _extract_target_function_name(code) == "test_ok"


def test_run_test_with_deterministic_seed_preamble_passes():
    """Ensure run_test executes the test function instead of seed helper (issue #330)."""
    code = f"{_PREAMBLE_WITH_DETERMINISTIC_SEED}\ndef test_math():\n    assert math.sqrt(16) == 4\n"
    passed, message = run_test(code, math)
    assert passed is True
    assert message == "Test passed."


def test_execute_test_explicit_function_name():
    code = "def test_first():\n    assert True\ndef test_second():\n    assert False\n"
    execution = execute_test(code, math, function_name="test_first")
    assert execution.function_name == "test_first"
    assert execution.error is None
    assert execution.message == "Test passed."
