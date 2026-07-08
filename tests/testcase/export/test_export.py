#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Tests for the libcst-based test-suite exporter (``pynguin.testcase.export``).

These tests target the current architecture: ``TestSuiteWriter`` renders a
``TestSuiteChromosome`` (a list of ``TestCaseChromosome``, each wrapping a
``pynguin.testcase.testcase.TestCase`` of libcst-backed ``Statement`` objects)
to a single pytest file. Failing statements are wrapped individually in
``with pytest.raises(...):`` rather than marking the whole test ``xfail``, and
an empty suite is rendered as a ``test_placeholder`` function.
"""

from __future__ import annotations

import os
import subprocess  # noqa: S404
import sys
from typing import TYPE_CHECKING
from unittest import mock

import libcst as cst

import pynguin.assertion.assertion as ass
import pynguin.ga.testcasechromosome as tcc
import pynguin.ga.testsuitechromosome as tsc
import pynguin.testcase.testcase as tc
from pynguin.testcase import export
from pynguin.testcase.export import TestSuiteWriter
from pynguin.utils.exceptions import TracingAbortedException
from pynguin.utils.naming import get_module_alias
from tests.testcase._builders import assign, int_stmt, make_test_case, stmt

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


class _CustomExportError(Exception):
    """A non-builtins exception used to test the exception-import rendering."""


def _code_of(node: cst.SimpleStatementLine | cst.BaseCompoundStatement) -> str:
    """Render a single CST node's source via a throwaway module.

    Args:
        node: The node to render.

    Returns:
        The rendered source string.
    """
    return cst.Module(body=[node]).code


# ---------------------------------------------------------------------------
# _build_test_function: statement-kind -> expected exported source
# ---------------------------------------------------------------------------


def test_build_test_function_plain_statement():
    """A statement with no exception and no assertions is rendered as-is."""
    writer = TestSuiteWriter()
    test_case = make_test_case(int_stmt("int_0", 5))

    func = writer._build_test_function(0, test_case, [None])

    assert func.name.value == "test_0"
    assert _code_of(func) == "def test_0():\n    int_0 = 5\n"


def test_build_test_function_with_object_assertion():
    """An assertion on a statement is rendered right after that statement."""
    writer = TestSuiteWriter()
    test_case = make_test_case(int_stmt("int_0", 5))
    test_case.get_statement(-1).assertions.append(ass.ObjectAssertion("int_0", 5))

    func = writer._build_test_function(0, test_case, [None])

    assert _code_of(func) == "def test_0():\n    int_0 = 5\n    assert int_0 == 5\n"


def test_build_test_function_exception_statement_wraps_pytest_raises():
    """A statement whose exc type is not None is wrapped in pytest.raises."""
    writer = TestSuiteWriter()
    test_case = make_test_case(
        assign("float_0", "42.23"),
        stmt("simple_function(float_0)"),
    )

    func = writer._build_test_function(0, test_case, [None, ValueError])

    assert _code_of(func) == (
        "def test_0():\n"
        "    float_0 = 42.23\n"
        "    with pytest.raises(ValueError):\n"
        "        simple_function(float_0)\n"
    )


def test_build_test_function_exception_statement_with_trailing_assertion():
    """An assertion attached to a raising statement is appended after the with-block.

    It is a sibling statement (not nested inside the ``with``), mirroring how
    ``ExceptionAssertion`` renders to nothing while other assertion kinds would
    still be emitted at the outer indentation level.
    """
    writer = TestSuiteWriter()
    test_case = make_test_case(stmt("some_call()"))
    test_case.get_statement(-1).assertions.append(ass.ObjectAssertion("var_0", 1))

    func = writer._build_test_function(0, test_case, [RuntimeError])

    assert _code_of(func) == (
        "def test_0():\n"
        "    with pytest.raises(RuntimeError):\n"
        "        some_call()\n"
        "    assert var_0 == 1\n"
    )


def test_build_test_function_exception_assertion_produces_no_extra_code():
    """ExceptionAssertion renders to no CST node, so only the with-block remains."""
    writer = TestSuiteWriter()
    test_case = make_test_case(stmt("some_call()"))
    test_case.get_statement(-1).assertions.append(ass.ExceptionAssertion("builtins", "ValueError"))

    func = writer._build_test_function(0, test_case, [ValueError])

    assert _code_of(func) == (
        "def test_0():\n    with pytest.raises(ValueError):\n        some_call()\n"
    )


def test_build_test_function_empty_statements_uses_placeholder_pass():
    """A TestCase with zero statements renders as a lone ``pass``."""
    writer = TestSuiteWriter()
    test_case = tc.TestCase()

    func = writer._build_test_function(0, test_case, [])

    assert _code_of(func) == "def test_0():\n    pass\n"


def test_build_test_function_raw_code_fallback_success(monkeypatch):
    """When statements() is empty but to_code() yields real source, it is parsed in."""
    writer = TestSuiteWriter()
    test_case = tc.TestCase()
    monkeypatch.setattr(test_case, "to_code", lambda: "x = 1\ny = 2\n")

    func = writer._build_test_function(0, test_case, [])

    assert _code_of(func) == "def test_0():\n    x = 1\n    y = 2\n"


def test_build_test_function_raw_code_fallback_invalid_syntax_suppressed(monkeypatch):
    """Invalid raw code is suppressed and falls back to a bare ``pass``."""
    writer = TestSuiteWriter()
    test_case = tc.TestCase()
    monkeypatch.setattr(test_case, "to_code", lambda: "def(:::not valid python")

    func = writer._build_test_function(0, test_case, [])

    assert _code_of(func) == "def test_0():\n    pass\n"


# ---------------------------------------------------------------------------
# to_code / to_test_function sanity (used throughout as the rendering oracle)
# ---------------------------------------------------------------------------


def test_to_code_renders_statements_in_order():
    test_case = make_test_case(int_stmt("int_0", 5), assign("int_1", "int_0 + 1"))

    assert test_case.to_code() == "int_0 = 5\nint_1 = int_0 + 1\n"


def test_to_code_empty_test_case_is_pass():
    assert tc.TestCase().to_code() == "pass\n"


# ---------------------------------------------------------------------------
# TestSuiteWriter.write(): empty-suite placeholder
# ---------------------------------------------------------------------------


def test_write_empty_suite_emits_placeholder(tmp_path: Path):
    module_name = "tests.fixtures.accessibles.accessible"
    writer = TestSuiteWriter()
    suite = tsc.TestSuiteChromosome()

    out_file = writer.write(suite, module_name, tmp_path, format_with_black=False)

    content = out_file.read_text(encoding="utf-8")
    assert "def test_placeholder():" in content
    assert "pass" in content
    assert "import pytest" not in content


# ---------------------------------------------------------------------------
# TestSuiteWriter.write(): exception rendering + non-builtins exception import
# ---------------------------------------------------------------------------


def test_write_wraps_raising_statement_and_imports_pytest(tmp_path: Path):
    module_name = "tests.fixtures.accessibles.accessible"
    module_alias = get_module_alias(module_name)
    writer = TestSuiteWriter()
    test_case = make_test_case(
        int_stmt("int_0", 5),
        assign("some_type_0", f"{module_alias}.SomeType(int_0)"),
    )
    suite = tsc.TestSuiteChromosome()
    suite.add_test_case_chromosome(tcc.TestCaseChromosome(test_case))

    with mock.patch.object(
        TestSuiteWriter,
        "_per_statement_exceptions",
        return_value=[None, ValueError],
    ):
        out_file = writer.write(suite, module_name, tmp_path, format_with_black=False)

    content = out_file.read_text(encoding="utf-8")
    assert "import pytest" in content
    assert "with pytest.raises(ValueError):" in content


def test_write_imports_non_builtins_exception_type(tmp_path: Path):
    module_name = "tests.fixtures.accessibles.accessible"
    writer = TestSuiteWriter()
    test_case = make_test_case(stmt("some_call()"))
    suite = tsc.TestSuiteChromosome()
    suite.add_test_case_chromosome(tcc.TestCaseChromosome(test_case))

    with mock.patch.object(
        TestSuiteWriter,
        "_per_statement_exceptions",
        return_value=[_CustomExportError],
    ):
        out_file = writer.write(suite, module_name, tmp_path, format_with_black=False)

    content = out_file.read_text(encoding="utf-8")
    assert f"from {__name__} import _CustomExportError" in content
    assert "with pytest.raises(_CustomExportError):" in content


# ---------------------------------------------------------------------------
# TestSuiteWriter.write(): nonexistent module (import failures, both call sites)
# ---------------------------------------------------------------------------


def test_write_nonexistent_module_falls_back_gracefully(tmp_path: Path):
    """Neither _per_statement_exceptions nor the public-names lookup can import.

    Exercises the ``sys.path`` insertion (via ``project_path``), the
    ``ImportError`` branch inside ``_per_statement_exceptions`` (which yields
    ``[None] * size``), and the writer's own failed ``importlib.import_module``
    (which leaves ``public_names`` empty and ``star_stmt`` as ``None``).
    """
    bogus_module = "pynguin_this_module_does_not_exist_at_all"
    writer = TestSuiteWriter()
    test_case = make_test_case(int_stmt("int_0", 5))
    suite = tsc.TestSuiteChromosome()
    suite.add_test_case_chromosome(tcc.TestCaseChromosome(test_case))

    out_file = writer.write(
        suite,
        bogus_module,
        tmp_path,
        project_path=str(tmp_path),
        format_with_black=False,
    )

    content = out_file.read_text(encoding="utf-8")
    assert f"import {bogus_module}" in content
    # No public names could be resolved, so no `from <module> import ...` line.
    assert f"from {bogus_module} import" not in content
    assert str(tmp_path) in sys.path


# ---------------------------------------------------------------------------
# TestSuiteWriter.write(): seeded output (patch preamble + reseed fixture)
# ---------------------------------------------------------------------------


def test_write_with_seed_emits_patch_preamble_and_fixture(tmp_path: Path):
    module_name = "tests.fixtures.accessibles.accessible"
    writer = TestSuiteWriter()
    test_case = make_test_case(int_stmt("int_0", 5))
    suite = tsc.TestSuiteChromosome()
    suite.add_test_case_chromosome(tcc.TestCaseChromosome(test_case))

    out_file = writer.write(suite, module_name, tmp_path, format_with_black=False, seed=42)

    content = out_file.read_text(encoding="utf-8")
    assert "import random" in content
    assert "__pynguin_patched__" in content
    assert "_pynguin_seed_random" in content
    assert "random.seed(42)" in content
    assert "import pytest" in content


# ---------------------------------------------------------------------------
# TestSuiteWriter.write(): black formatting failure is tolerated
# ---------------------------------------------------------------------------


def test_write_tolerates_black_invalid_input(tmp_path: Path, caplog: pytest.LogCaptureFixture):
    from black.parsing import InvalidInput  # noqa: PLC0415

    module_name = "tests.fixtures.accessibles.accessible"
    writer = TestSuiteWriter()
    test_case = make_test_case(int_stmt("int_0", 5))
    suite = tsc.TestSuiteChromosome()
    suite.add_test_case_chromosome(tcc.TestCaseChromosome(test_case))

    with (
        mock.patch("black.format_str", side_effect=InvalidInput("nope")),
        caplog.at_level("WARNING"),
    ):
        out_file = writer.write(suite, module_name, tmp_path, format_with_black=True)

    content = out_file.read_text(encoding="utf-8")
    # Falls back to the unformatted (but still valid/parseable) source.
    assert "def test_0" in content
    compile(content, str(out_file), "exec")
    assert "Could not format the module" in caplog.text


# ---------------------------------------------------------------------------
# Integration: export a real test case to a file and run it under pytest
# ---------------------------------------------------------------------------


def test_export_integration_generated_file_passes_under_pytest(tmp_path: Path):
    # Use a self-contained SUT written into tmp_path. A freshly created module in a
    # temporary directory cannot have been left globally instrumented by another test
    # in the suite. That matters because ``TestSuiteWriter.write`` re-executes each
    # statement (in a watchdog thread) to detect real SUT exceptions; when the SUT
    # module happens to be globally instrumented, the re-execution trips the tracer's
    # thread-identity guard and the statement is mis-wrapped in a bogus
    # ``pytest.raises(TracingAbortedException)`` (the guarded path only protects this
    # when ``subject_properties`` is supplied). See the product-bug note in the handoff.
    module_name = "export_integration_sut"
    (tmp_path / f"{module_name}.py").write_text(
        "class SomeType:\n"
        "    def __init__(self, value):\n"
        "        self.value = value\n"
        "\n"
        "    def simple_method(self, factor):\n"
        "        return float(self.value * factor * 5)\n",
        encoding="utf-8",
    )
    module_alias = get_module_alias(module_name)
    writer = TestSuiteWriter()

    test_case = make_test_case(
        int_stmt("int_0", 5),
        assign("some_type_0", f"{module_alias}.SomeType(int_0)"),
        int_stmt("int_1", 3),
        assign("float_0", "some_type_0.simple_method(int_1)"),
    )
    # simple_method multiplies value by factor by five, so the result is 75.0
    test_case.get_statement(-1).assertions.append(ass.FloatAssertion("float_0", 75.0))

    suite = tsc.TestSuiteChromosome()
    suite.add_test_case_chromosome(tcc.TestCaseChromosome(test_case))

    out_file = writer.write(
        suite,
        module_name,
        tmp_path,
        project_path=str(tmp_path),
        format_with_black=False,
    )

    assert out_file.exists()

    # Strip pytest-cov / coverage env vars so the child pytest does not hook coverage:
    # otherwise it writes statement-mode data that the parent (branch mode) cannot
    # combine ("Can't combine statement coverage data with branch data").
    child_env = {k: v for k, v in os.environ.items() if not k.startswith(("COV_CORE", "COVERAGE"))}
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-m", "pytest", "-p", "no:randomly", "-q", str(out_file)],
        cwd=str(tmp_path),
        env=child_env,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )

    assert result.returncode == 0, (
        f"generated test file failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )
    assert "1 passed" in result.stdout


# ---------------------------------------------------------------------------
# _exec_statement_guarded / _per_statement_exceptions internals
# ---------------------------------------------------------------------------


def test_exec_statement_guarded_without_tracer_runs_statement():
    namespace: dict = {"__builtins__": __builtins__}

    finished, exc_type = export._exec_statement_guarded("x = 1 + 1\n", namespace, None)

    assert finished is True
    assert exc_type is None
    assert namespace["x"] == 2


def test_exec_statement_guarded_captures_exception():
    namespace: dict = {"__builtins__": __builtins__}

    finished, exc_type = export._exec_statement_guarded(
        "raise ValueError('boom')\n", namespace, None
    )

    assert finished is True
    assert exc_type is ValueError


def test_exec_statement_guarded_tracing_aborted_is_inconclusive():
    """A TracingAbortedException during detection is treated as inconclusive.

    It must not be recorded as the statement's exception (which would emit a bogus
    pytest.raises wrapper). This reproduces the condition where the SUT is globally
    instrumented: the injected tracer guard raises TracingAbortedException on the
    watchdog thread, and the guarded exec must return (finished=False, exc=None).
    """

    def _boom():
        raise TracingAbortedException("thread-identity guard")

    namespace: dict = {"__builtins__": __builtins__, "boom": _boom}

    finished, exc_type = export._exec_statement_guarded("x = boom()\n", namespace, None)

    assert finished is False
    assert exc_type is None


def test_exec_statement_guarded_timeout(monkeypatch):
    monkeypatch.setattr(export, "_STATEMENT_EXECUTION_TIMEOUT", 0.05)
    namespace: dict = {"__builtins__": __builtins__}

    finished, exc_type = export._exec_statement_guarded(
        "import time\ntime.sleep(2)\n", namespace, None
    )

    assert finished is False
    assert exc_type is None


def test_per_statement_exceptions_inserts_project_path(tmp_path: Path):
    writer = TestSuiteWriter()
    test_case = make_test_case(int_stmt("int_0", 5))
    project_path = str(tmp_path / "nonexistent_sys_path_dir")

    writer._per_statement_exceptions(
        test_case, "tests.fixtures.accessibles.accessible", project_path
    )

    assert project_path in sys.path


def test_per_statement_exceptions_unimportable_module_returns_all_none():
    writer = TestSuiteWriter()
    test_case = make_test_case(int_stmt("int_0", 5), int_stmt("int_1", 6))

    result = writer._per_statement_exceptions(
        test_case, "pynguin_definitely_not_a_real_module", None
    )

    assert result == [None, None]


def test_per_statement_exceptions_records_real_exception():
    module_name = "tests.fixtures.accessibles.accessible"
    module_alias = get_module_alias(module_name)
    writer = TestSuiteWriter()
    test_case = make_test_case(
        assign("float_0", "42.23"),
        stmt(f"{module_alias}.simple_function(float_0, extra_bad_arg=1)"),
    )

    result = writer._per_statement_exceptions(test_case, module_name, None)

    assert result[0] is None
    assert result[1] is TypeError


def test_per_statement_exceptions_timeout_marks_remaining_clean(monkeypatch):
    monkeypatch.setattr(export, "_STATEMENT_EXECUTION_TIMEOUT", 0.05)
    writer = TestSuiteWriter()
    test_case = make_test_case(
        stmt("import time"),
        stmt("time.sleep(2)"),
        int_stmt("int_0", 5),
    )

    result = writer._per_statement_exceptions(
        test_case, "tests.fixtures.accessibles.accessible", None
    )

    assert result == [None, None, None]


def test_per_statement_exceptions_rebinds_tracer_thread_guard(subject_properties):
    """When subject_properties is given, the tracer is rebound to the watchdog thread.

    Covers the ``with tracer, tracer.temporarily_disable():`` branch, which exists so
    the statement is re-executed without the shared tracer's thread-identity guard
    aborting it (it would otherwise misreport a ``TracingAbortedException``).
    """
    writer = TestSuiteWriter()
    test_case = make_test_case(int_stmt("int_0", 5))

    result = writer._per_statement_exceptions(
        test_case,
        "tests.fixtures.accessibles.accessible",
        None,
        subject_properties=subject_properties,
    )

    assert result == [None]
