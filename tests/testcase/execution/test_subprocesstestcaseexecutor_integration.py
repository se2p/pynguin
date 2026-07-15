#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Integration tests for :class:`SubprocessTestCaseExecutor`.

These tests drive libcst-backed test cases through the public
``SubprocessTestCaseExecutor.execute`` entry point end-to-end, i.e. each test case is
actually executed inside a separate subprocess. They cover the same scenarios as the
in-process integration tests in :mod:`test_testcaseexecutor_integration` but exercise
the subprocess path:

* the per-statement execution loop running each statement in a subprocess,
* an exception in a statement being captured and breaking the loop,
* the subprocess result matching the in-process result for the same test case,
* the crash-test-generation integration path (kept skipped for CI, see below).

The two crash-generation tests remain skipped: they either crash the main thread on CI
or are inherently flaky, exactly as before the migration to the libcst representation.
"""

from __future__ import annotations

import contextlib
import importlib
from typing import TYPE_CHECKING

import pytest

import pynguin.configuration as config
import pynguin.ga.generationalgorithmfactory as gaf
from pynguin.analyses.module import generate_test_cluster
from pynguin.instrumentation.machinery import install_import_hook
from pynguin.instrumentation.tracer import SubjectProperties
from pynguin.testcase.execution import SubprocessTestCaseExecutor, TestCaseExecutor
from tests.testcase._builders import assign, make_test_case, stmt

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path


MODULE_ACCESSIBLE = "tests.fixtures.accessibles.accessible"
MODULE_TRIANGLE = "tests.fixtures.examples.triangle"


@contextlib.contextmanager
def _subprocess_executor_for(
    module_name: str, subject_properties: SubjectProperties
) -> Iterator[SubprocessTestCaseExecutor]:
    """Install the import hook, (re)load *module_name* instrumented, yield an executor.

    The module is imported and reloaded inside the instrumentation tracer context so the
    instrumentation is applied, while the executor itself runs afterwards (outside that
    context but inside the import hook).
    """
    config.configuration.module_name = module_name
    with install_import_hook(module_name, subject_properties):
        with subject_properties.instrumentation_tracer:
            module = importlib.import_module(module_name)
            importlib.reload(module)
        yield SubprocessTestCaseExecutor(subject_properties)


# --------------------------------------------------------------------------- #
# _build_namespace: module members, module alias, pytest and builtins bindings
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("module_name", "code"),
    [
        # Public members of the SUT module are bound directly.
        (MODULE_ACCESSIBLE, "obj = SomeType(1.0)"),
        (MODULE_ACCESSIBLE, "val = simple_function(2.0)"),
        # The SUT module is also reachable through its generated alias.
        (MODULE_ACCESSIBLE, "val = accessible_.simple_function(2.0)"),
        # pytest and builtins are always available in the namespace.
        (MODULE_ACCESSIBLE, "size = len((1, 2, 3))"),
        # The alias is derived from the configured module name, not hard-coded.
        (MODULE_TRIANGLE, "res = triangle(2, 3, 4)"),
    ],
)
def test_build_namespace_binding(
    module_name: str, code: str, subject_properties: SubjectProperties
) -> None:
    """Each statement resolves its names against the built namespace in the subprocess."""
    with _subprocess_executor_for(module_name, subject_properties) as executor:
        result = executor.execute(make_test_case(stmt(code)))
    assert not result.has_test_exceptions()


# --------------------------------------------------------------------------- #
# Per-statement execution loop + statement-execution counter
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("size", [1, 2, 3])
def test_per_statement_loop_runs_every_statement(
    size: int, subject_properties: SubjectProperties
) -> None:
    """A multi-statement test case runs to completion in the subprocess without errors.

    The statement-execution counter is populated by a local observer during in-process
    execution and is not propagated across the subprocess boundary, so it cannot be
    asserted here; the absence of captured exceptions confirms every statement ran.
    """
    test_case = make_test_case(*(assign(f"var_{i}", str(i), bound_type=int) for i in range(size)))
    with _subprocess_executor_for(MODULE_ACCESSIBLE, subject_properties) as executor:
        result = executor.execute(test_case)
    assert not result.has_test_exceptions()
    assert result.exceptions == {}


def test_clean_test_case_has_no_exceptions(
    subject_properties: SubjectProperties,
) -> None:
    """A test case whose statements all succeed reports no exceptions from the subprocess."""
    test_case = make_test_case(
        assign("var_0", "5", bound_type=int),
        assign("var_1", "var_0 + 1", bound_type=int),
    )
    with _subprocess_executor_for(MODULE_ACCESSIBLE, subject_properties) as executor:
        result = executor.execute(test_case)
    assert not result.has_test_exceptions()
    assert result.exceptions == {}


# --------------------------------------------------------------------------- #
# Exception capture + break out of the execution loop
# --------------------------------------------------------------------------- #
def test_exception_captured_and_breaks_execution(
    subject_properties: SubjectProperties,
) -> None:
    """An exception is captured for its statement and stops the following statements."""
    test_case = make_test_case(
        assign("var_0", "1", bound_type=int),  # idx 0: succeeds
        stmt("bad = 1 / 0"),  # idx 1: raises
        assign("var_2", "2", bound_type=int),  # idx 2: must NOT run
    )
    with _subprocess_executor_for(MODULE_ACCESSIBLE, subject_properties) as executor:
        result = executor.execute(test_case)

    assert result.has_test_exceptions()
    assert result.get_first_position_of_thrown_exception() == 1
    assert isinstance(result.exceptions[1], ZeroDivisionError)
    # The loop broke: the statement after the failing one was never reached.
    assert 2 not in result.exceptions


def test_exception_at_first_statement_reports_index_zero(
    subject_properties: SubjectProperties,
) -> None:
    """A failure in the first statement is reported at index 0 and stops execution."""
    test_case = make_test_case(
        stmt("bad = 1 / 0"),  # idx 0: raises immediately
        assign("var_1", "1", bound_type=int),  # idx 1: must NOT run
    )
    with _subprocess_executor_for(MODULE_ACCESSIBLE, subject_properties) as executor:
        result = executor.execute(test_case)
    assert result.get_first_position_of_thrown_exception() == 0
    assert set(result.exceptions) == {0}


# --------------------------------------------------------------------------- #
# Subprocess result parity with in-process execution
# --------------------------------------------------------------------------- #
def test_subprocess_result_matches_in_process_result(
    subject_properties: SubjectProperties,
) -> None:
    """Executing the same test case in-process and in a subprocess yields equal results."""
    test_case = make_test_case(
        assign("var_0", "3", bound_type=int),
        assign("var_1", "var_0 * 2", bound_type=int),
        assign("var_2", "simple_function(1.0)", bound_type=float),
    )

    config.configuration.module_name = MODULE_ACCESSIBLE
    with install_import_hook(MODULE_ACCESSIBLE, subject_properties):
        with subject_properties.instrumentation_tracer:
            module = importlib.import_module(MODULE_ACCESSIBLE)
            importlib.reload(module)
        in_process_result = TestCaseExecutor(subject_properties).execute(test_case)

    with install_import_hook(MODULE_ACCESSIBLE, subject_properties):
        with subject_properties.instrumentation_tracer:
            module = importlib.import_module(MODULE_ACCESSIBLE)
            importlib.reload(module)
        subprocess_result = SubprocessTestCaseExecutor(subject_properties).execute(test_case)

    assert in_process_result == subprocess_result


# --------------------------------------------------------------------------- #
# Crash-test-generation integration (kept skipped, see module docstring)
# --------------------------------------------------------------------------- #
@pytest.fixture
def crash_test_expected(tmp_path: Path) -> Path:
    expected_content = """# Test cases automatically generated by Pynguin (https://www.pynguin.eu).
# Please check them before you use them.
import tests.fixtures.crash.seg_fault as module_0


def test_case_0():
    module_0.cause_segmentation_fault()
"""
    crash_file = tmp_path / "crash_test_expected.py"
    crash_file.write_text(expected_content)
    return crash_file


@pytest.mark.skip(reason="Makes main thread on GitHub Actions crash")
def test_generate_crashing_test_integration(tmp_path: Path, crash_test_expected: Path) -> None:
    module_name = "tests.fixtures.crash.seg_fault"
    crash_path = tmp_path / "crashing_tests_seg_fault"
    crash_path.mkdir(parents=True, exist_ok=True)
    config.configuration.test_case_output.crash_path = str(crash_path)

    config.configuration.stopping.maximum_iterations = 10
    config.configuration.module_name = module_name
    config.configuration.search_algorithm.min_initial_tests = 2
    config.configuration.search_algorithm.max_initial_tests = 2
    config.configuration.search_algorithm.population = 2
    config.configuration.test_creation.none_weight = 1
    config.configuration.test_creation.any_weight = 1
    subject_properties = SubjectProperties()
    with install_import_hook(module_name, subject_properties):
        # Need to force reload in order to apply instrumentation.
        with subject_properties.instrumentation_tracer:
            module = importlib.import_module(module_name)
            importlib.reload(module)

        executor = SubprocessTestCaseExecutor(subject_properties)
        cluster = generate_test_cluster(module_name)
        search_algorithm = gaf.TestSuiteGenerationAlgorithmFactory(
            executor, cluster
        ).get_search_algorithm()
        test_cases = search_algorithm.generate_tests()
        assert test_cases.size() == 0

    # Check that the crashing_tests dir contains one file and compare its content
    assert crash_path.exists()
    assert len(list(crash_path.iterdir())) == 1
    crash_file = next(crash_path.iterdir())
    assert crash_file.is_file()
    assert crash_file.read_text() == crash_test_expected.read_text()


@pytest.mark.skip(reason="Flaky")
def test_generate_partly_crashing_test_integration(tmp_path: Path) -> None:
    module_name = "tests.fixtures.crash.partly_crashing"
    crash_path = tmp_path / "crashing_tests_partly_crashing"
    crash_path.mkdir(parents=True, exist_ok=True)
    config.configuration.test_case_output.crash_path = str(crash_path)

    config.configuration.stopping.maximum_iterations = 10
    config.configuration.module_name = module_name
    config.configuration.search_algorithm.min_initial_tests = 2
    config.configuration.search_algorithm.max_initial_tests = 2
    config.configuration.search_algorithm.population = 2
    config.configuration.test_creation.none_weight = 1
    config.configuration.test_creation.any_weight = 1
    subject_properties = SubjectProperties()
    with install_import_hook(module_name, subject_properties):
        # Need to force reload in order to apply instrumentation.
        with subject_properties.instrumentation_tracer:
            module = importlib.import_module(module_name)
            importlib.reload(module)

        executor = SubprocessTestCaseExecutor(subject_properties)
        cluster = generate_test_cluster(module_name)
        search_algorithm = gaf.TestSuiteGenerationAlgorithmFactory(
            executor, cluster
        ).get_search_algorithm()
        test_cases = search_algorithm.generate_tests()
        assert test_cases.size() >= 1

    # Check that the crashing_tests dir contains one file and compare its content
    assert crash_path.exists()
    assert len(list(crash_path.iterdir())) >= 1
    crash_file = next(crash_path.iterdir())
    assert crash_file.is_file()
