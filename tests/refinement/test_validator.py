#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Tests for the in-process test execution validator (validator.py)."""

from __future__ import annotations

import math
import random
import sys
import threading
import time
import types

import libcst as cst
import pytest

import pynguin.configuration as config
from pynguin.generator import _patch_random  # noqa: PLC2701
from pynguin.refinement.validator import (
    TestExecutionTimeoutError,
    _ensure_module_package_on_path,  # noqa: PLC2701
    call_test_functions,
    collect_test_functions,
    find_test_function_name,
    preserved_random_seed,
    resolve_timeout,
    run_test,
    time_limit,
)
from pynguin.testcase.export import TestSuiteWriter
from pynguin.utils import randomness


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


def _seed_preamble(seed: int) -> str:
    """The deterministic-seed preamble the exporter writes for SUTs using ``random``."""
    body = TestSuiteWriter._create_patch_nodes(seed) + TestSuiteWriter._create_seed_fixture(seed)
    return "import pytest\nimport random as _pynguin_random\n" + cst.Module(body=body).code


def _value_under_seed(seed: int) -> int:
    rng = random.Random(seed)  # noqa: S311
    return rng.randint(1, 10**9)


def test_find_test_function_name_skips_seed_preamble():
    code = f"{_seed_preamble(42)}\ndef test_case_0():\n    assert True\n"
    assert find_test_function_name(code) == "test_case_0"


def test_find_test_function_name_prefers_last_test():
    code = "def test_1():\n    pass\ndef helper():\n    pass\ndef test_2():\n    pass\n"
    assert find_test_function_name(code) == "test_2"


def test_find_test_function_name_falls_back_to_last_function():
    code = "def _helper():\n    pass\ndef renamed():\n    pass\n"
    assert find_test_function_name(code) == "renamed"


def test_find_test_function_name_ignores_nested_defs():
    code = "def _helper():\n    def test_inner():\n        pass\ndef check():\n    pass\n"
    assert find_test_function_name(code) == "check"


def test_find_test_function_name_syntax_error():
    code = "def _helper(:\n    pass\ndef test_ok():\n    pass\n    def test_nested(): pass\n"
    assert find_test_function_name(code) == "test_ok"


def test_find_test_function_name_none():
    assert not find_test_function_name("x = 1\n")


def test_run_test_reseeds_like_autouse_fixture():
    """A seed-dependent assertion passes, as under pytest, whatever the random state."""
    code = (
        f"{_seed_preamble(42)}\n"
        "def test_case_0():\n"
        f"    assert random.randint(1, 10**9) == {_value_under_seed(42)}\n"
    )
    random.seed(7)
    assert run_test(code, random) == (True, "Test passed.")
    assert run_test(code, random) == (True, "Test passed.")


def test_run_test_reverts_seed_patch():
    original_seed = random.Random.seed
    code = f"{_seed_preamble(42)}\ndef test_case_0():\n    assert True\n"
    assert run_test(code, random)[0]
    assert random.Random.seed is original_seed


def test_run_test_reverts_seed_patch_on_failure():
    original_seed = random.Random.seed
    code = f"{_seed_preamble(42)}\ndef test_case_0():\n    assert False\n"
    assert not run_test(code, random)[0]
    assert random.Random.seed is original_seed


def test_call_test_functions_reseeds_before_each_test():
    expected = _value_under_seed(42)
    code = (
        f"{_seed_preamble(42)}\n"
        "def test_a():\n"
        f"    assert random.randint(1, 10**9) == {expected}\n"
        "def test_b():\n"
        "    rng = random.Random()\n"
        f"    assert random.randint(1, 10**9) == {expected}\n"
        "    assert rng.randint(1, 10**9) == "
        f"{_value_under_seed(42)}\n"
    )
    original_seed = random.Random.seed
    scope: dict = {"random": random}
    with preserved_random_seed():
        exec(code, scope)  # noqa: S102
        call_test_functions(scope, collect_test_functions(code))
    assert random.Random.seed is original_seed


def test_run_test_reseeds_sut_instances_tracked_by_pynguin(monkeypatch):
    """A SUT-level ``Random()`` created under Pynguin's own patch is reseeded too."""
    monkeypatch.setattr(config.configuration.seeding, "seed", 42)
    with preserved_random_seed():
        _patch_random()
        sut = types.ModuleType("sut_with_rng")
        sut.rng = random.Random()  # noqa: S311
        sut.rng.random()  # state advanced, as by test generation
        rng_state = randomness.RNG.getstate()
        code = (
            f"{_seed_preamble(42)}\n"
            "def test_case_0():\n"
            f"    assert sut_with_rng.rng.randint(1, 10**9) == {_value_under_seed(42)}\n"
        )
        assert run_test(code, sut) == (True, "Test passed.")
        assert run_test(code, sut) == (True, "Test passed.")
        assert randomness.RNG.getstate() == rng_state
