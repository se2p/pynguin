#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Integration tests for the per-statement execution core of :class:`TestCaseExecutor`.

These tests drive real fixture modules through the public ``TestCaseExecutor.execute``
entry point (statements run inside a watchdog thread, so internals must not be called
directly). They cover the per-statement execution core only:

* ``_build_namespace`` exposing the SUT module's members, its alias, ``pytest`` and
  builtins,
* the per-statement execution loop running each statement in order,
* an exception in a statement being captured and breaking the loop,
* the statement-execution counter incrementing correctly.

Disabled subsystems (return-type / type tracing, per-statement assertion execution,
dynamic slicing, subprocess execution) are intentionally out of scope.
"""

from __future__ import annotations

import contextlib
import importlib
from typing import TYPE_CHECKING

import pytest

import pynguin.configuration as config
from pynguin.ga.stoppingcondition import MaxStatementExecutionsStoppingCondition
from pynguin.instrumentation.machinery import install_import_hook
from pynguin.testcase.execution import TestCaseExecutor
from tests.testcase._builders import assign, make_test_case, stmt

if TYPE_CHECKING:
    from collections.abc import Iterator

    from pynguin.instrumentation.tracer import SubjectProperties

MODULE_ACCESSIBLE = "tests.fixtures.accessibles.accessible"
MODULE_TRIANGLE = "tests.fixtures.examples.triangle"


@contextlib.contextmanager
def _executor_for(
    module_name: str, subject_properties: SubjectProperties
) -> Iterator[TestCaseExecutor]:
    """Install the import hook, (re)load *module_name* instrumented, yield an executor.

    Mirrors the canonical set-up: the module is imported and reloaded inside the
    instrumentation tracer context so the instrumentation is applied, while the
    executor itself runs afterwards (outside that context but inside the import hook).
    """
    config.configuration.module_name = module_name
    with install_import_hook(module_name, subject_properties):
        with subject_properties.instrumentation_tracer:
            module = importlib.import_module(module_name)
            importlib.reload(module)
        yield TestCaseExecutor(subject_properties)


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
        (MODULE_ACCESSIBLE, "obj = accessible_.SomeType(3.0)"),
        # pytest and builtins are always available in the namespace.
        (MODULE_ACCESSIBLE, "name = pytest.__name__"),
        (MODULE_ACCESSIBLE, "size = len((1, 2, 3))"),
        # The alias is derived from the configured module name, not hard-coded.
        (MODULE_TRIANGLE, "res = triangle_.triangle(1, 1, 1)"),
        (MODULE_TRIANGLE, "res = triangle(2, 3, 4)"),
    ],
)
def test_build_namespace_binding(
    module_name: str, code: str, subject_properties: SubjectProperties
) -> None:
    """Each statement resolves its names against the built namespace without error."""
    with _executor_for(module_name, subject_properties) as executor:
        result = executor.execute(make_test_case(stmt(code)))
    assert not result.has_test_exceptions()


# --------------------------------------------------------------------------- #
# Per-statement execution loop + statement-execution counter
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("size", [1, 2, 3, 5])
def test_per_statement_loop_runs_and_counts_each_statement(
    size: int, subject_properties: SubjectProperties
) -> None:
    """Every statement is executed once and the execution counter matches the size."""
    condition = MaxStatementExecutionsStoppingCondition(10_000)
    test_case = make_test_case(*(assign(f"var_{i}", str(i), bound_type=int) for i in range(size)))
    with _executor_for(MODULE_ACCESSIBLE, subject_properties) as executor:
        executor.add_observer(condition)
        result = executor.execute(test_case)
    assert not result.has_test_exceptions()
    assert result.num_executed_statements == size
    assert condition.current_value() == size


def test_clean_test_case_has_no_exceptions(
    subject_properties: SubjectProperties,
) -> None:
    """A test case whose statements all succeed reports no exceptions."""
    test_case = make_test_case(
        assign("var_0", "5", bound_type=int),
        assign("var_1", "var_0 + 1", bound_type=int),
    )
    with _executor_for(MODULE_ACCESSIBLE, subject_properties) as executor:
        result = executor.execute(test_case)
    assert not result.has_test_exceptions()
    assert result.exceptions == {}


# --------------------------------------------------------------------------- #
# Exception capture + break out of the execution loop
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("bad_code", "exc_type"),
    [
        ("bad = 1 / 0", ZeroDivisionError),
        ("bad = undefined_name_zzz", NameError),
        ("bad = [][5]", IndexError),
        ("bad = int('not-an-int')", ValueError),
    ],
)
def test_exception_captured_and_breaks_execution(
    bad_code: str, exc_type: type[BaseException], subject_properties: SubjectProperties
) -> None:
    """An exception is captured for its statement and stops the following statements."""
    condition = MaxStatementExecutionsStoppingCondition(10_000)
    test_case = make_test_case(
        assign("var_0", "1", bound_type=int),  # idx 0: succeeds
        stmt(bad_code),  # idx 1: raises
        assign("var_2", "2", bound_type=int),  # idx 2: must NOT run
    )
    with _executor_for(MODULE_ACCESSIBLE, subject_properties) as executor:
        executor.add_observer(condition)
        result = executor.execute(test_case)

    assert result.has_test_exceptions()
    assert result.get_first_position_of_thrown_exception() == 1
    assert isinstance(result.exceptions[1], exc_type)
    # The loop broke: the statement after the failing one was never reached.
    assert 2 not in result.exceptions
    # Counter: idx 0 and idx 1 started, idx 2 was skipped by the break.
    assert result.num_executed_statements == 2
    assert condition.current_value() == 2


def test_exception_at_first_statement_reports_index_zero(
    subject_properties: SubjectProperties,
) -> None:
    """A failure in the first statement is reported at index 0 and stops execution."""
    test_case = make_test_case(
        stmt("bad = 1 / 0"),  # idx 0: raises immediately
        assign("var_1", "1", bound_type=int),  # idx 1: must NOT run
    )
    with _executor_for(MODULE_ACCESSIBLE, subject_properties) as executor:
        result = executor.execute(test_case)
    assert result.get_first_position_of_thrown_exception() == 0
    assert set(result.exceptions) == {0}
