#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Tests for the assertion-execution observer and assertion slicing.

Field/static-field assertions (``FieldReference`` / ``StaticFieldReference``)
are a disabled subsystem on this branch (see DISABLED_SUBSYSTEMS.md items
10-12); the corresponding main fixtures were dropped. Everything else is
ported to the libcst ``Statement``/``_make_statement`` representation, reusing
the shared conftest fixtures that already build assertion-carrying test
cases.
"""

import importlib
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import pynguin.configuration as config
import pynguin.ga.testcasechromosome as tcc
import pynguin.ga.testsuitechromosome as tsc
import pynguin.slicer.executionflowbuilder as efb
from pynguin.ga.checked_coverage import compute_assertion_checked_lines
from pynguin.ga.computations import TestSuiteAssertionCheckedCoverageFunction
from pynguin.instrumentation.machinery import install_import_hook
from pynguin.instrumentation.tracer import SubjectProperties
from pynguin.slicer.dynamicslicer import AssertionSlicer, DynamicSlicer
from pynguin.testcase.execution import RemoteAssertionExecutionObserver, TestCaseExecutor


@pytest.fixture
def partial_cover_plus_testsuite(
    plus_test_with_float_assertion, plus_test_with_multiple_assertions
) -> tsc.TestSuiteChromosome:
    test_case_1 = tcc.TestCaseChromosome(plus_test_with_float_assertion)
    test_case_2 = tcc.TestCaseChromosome(plus_test_with_multiple_assertions)
    test_suite = tsc.TestSuiteChromosome()
    test_suite.add_test_case_chromosome(test_case_1)
    test_suite.add_test_case_chromosome(test_case_2)
    return test_suite


@pytest.fixture
def no_cover_plus_testsuite(default_test_case) -> tsc.TestSuiteChromosome:
    test_suite = tsc.TestSuiteChromosome()
    test_suite.add_test_case_chromosome(tcc.TestCaseChromosome(default_test_case))
    return test_suite


@pytest.mark.parametrize(
    "module_name, test_case_name, expected_assertions",
    [
        ("tests.fixtures.linecoverage.plus", "plus_test_with_object_assertion", 1),
        ("tests.fixtures.linecoverage.plus", "plus_test_with_float_assertion", 1),
        ("tests.fixtures.linecoverage.plus", "plus_test_with_type_name_assertion", 1),
        ("tests.fixtures.linecoverage.plus", "plus_test_with_isinstance_assertion", 1),
        ("tests.fixtures.linecoverage.plus", "plus_test_with_multiple_assertions", 3),
        (
            "tests.fixtures.linecoverage.exception",
            "exception_test_with_except_assertion",
            1,
        ),
        ("tests.fixtures.linecoverage.list", "list_test_with_len_assertion", 1),
    ],
)
def test_assertion_detection_on_test_case(
    module_name,
    test_case_name,
    expected_assertions,
    request,
    subject_properties: SubjectProperties,
):
    test_case = request.getfixturevalue(test_case_name)
    config.configuration.module_name = module_name
    config.configuration.search_algorithm.coverage_metrics = [config.CoverageMetric.CHECKED]

    with install_import_hook(module_name, subject_properties):
        with subject_properties.instrumentation_tracer:
            module = importlib.import_module(module_name)
            importlib.reload(module)

        executor = TestCaseExecutor(subject_properties)
        executor.set_instrument(True)
        executor.add_remote_observer(RemoteAssertionExecutionObserver())
        result = executor.execute(test_case)
        assert result.execution_trace.executed_assertions
        assert len(result.execution_trace.executed_assertions) == expected_assertions


@pytest.mark.parametrize(
    "module_name, test_case_name",
    [
        ("tests.fixtures.linecoverage.plus", "plus_test_with_object_assertion"),
        ("tests.fixtures.linecoverage.plus", "plus_test_with_float_assertion"),
        ("tests.fixtures.linecoverage.plus", "plus_test_with_isinstance_assertion"),
        ("tests.fixtures.linecoverage.plus", "plus_test_with_multiple_assertions"),
    ],
)
def test_slicing_after_test_execution(
    module_name, test_case_name, request, subject_properties: SubjectProperties
):
    test_case = request.getfixturevalue(test_case_name)
    config.configuration.module_name = module_name
    config.configuration.search_algorithm.coverage_metrics = [config.CoverageMetric.CHECKED]

    with install_import_hook(module_name, subject_properties):
        with subject_properties.instrumentation_tracer:
            module = importlib.import_module(module_name)
            importlib.reload(module)

        executor = TestCaseExecutor(subject_properties)
        executor.set_instrument(True)
        executor.add_remote_observer(RemoteAssertionExecutionObserver())
        result = executor.execute(test_case)
        assert result.execution_trace.executed_assertions

        instructions_in_slice = []
        assertion_slicer = AssertionSlicer(subject_properties.existing_code_objects)
        for assertion in result.execution_trace.executed_assertions:
            instructions_in_slice.extend(
                assertion_slicer.slice_assertion(assertion, result.execution_trace)
            )
        assert instructions_in_slice

        checked_lines = DynamicSlicer.map_instructions_to_lines(
            instructions_in_slice, subject_properties
        )
        assert checked_lines


@pytest.mark.parametrize(
    "module_name, test_suite_name, expected_coverage",
    [
        (
            "tests.fixtures.linecoverage.plus",
            "no_cover_plus_testsuite",
            0,
        ),
        (
            "tests.fixtures.linecoverage.plus",
            "partial_cover_plus_testsuite",
            # covers only one method
            5 / 8,
        ),
    ],
)
def test_testsuite_assertion_checked_coverage_calculation(
    module_name,
    test_suite_name,
    expected_coverage,
    request,
    subject_properties: SubjectProperties,
):
    test_suite = request.getfixturevalue(test_suite_name)
    config.configuration.module_name = module_name
    config.configuration.search_algorithm.coverage_metrics = [
        config.CoverageMetric.CHECKED,
    ]

    with install_import_hook(module_name, subject_properties):
        with subject_properties.instrumentation_tracer:
            module = importlib.import_module(module_name)
            importlib.reload(module)

        executor = TestCaseExecutor(subject_properties)
        executor.set_instrument(True)
        executor.add_remote_observer(RemoteAssertionExecutionObserver())
        ff = TestSuiteAssertionCheckedCoverageFunction(executor)
        assert ff.compute_coverage(test_suite) == pytest.approx(expected_coverage, 0.1, 0.1)


def test_exception_only_statement_records_single_assertion(
    exception_test_with_except_assertion, subject_properties: SubjectProperties
):
    """Exception-only statements record exactly one ExecutedAssertion.

    The recorded assertion points at the raising call, via
    track_exception_assertion.
    """
    module_name = "tests.fixtures.linecoverage.exception"
    config.configuration.module_name = module_name
    config.configuration.search_algorithm.coverage_metrics = [config.CoverageMetric.CHECKED]

    with install_import_hook(module_name, subject_properties):
        with subject_properties.instrumentation_tracer:
            module = importlib.import_module(module_name)
            importlib.reload(module)

        executor = TestCaseExecutor(subject_properties)
        executor.set_instrument(True)
        executor.add_remote_observer(RemoteAssertionExecutionObserver())
        result = executor.execute(exception_test_with_except_assertion)

        assert len(result.execution_trace.executed_assertions) == 1
        executed_assertion = result.execution_trace.executed_assertions[0]
        assert (
            executed_assertion.trace_position
            == len(result.execution_trace.executed_instructions) - 1
        )


def test_raising_statement_without_exception_assertion_records_nothing(
    subject_properties: SubjectProperties,
):
    """Raising statements without an ExceptionAssertion record nothing.

    A statement that raises without carrying an ExceptionAssertion should
    not produce an ExecutedAssertion (see the RemoteAssertionExecutionObserver
    docstring).
    """
    module_name = "tests.fixtures.linecoverage.plus"
    import pynguin.testcase.testcase as tc  # noqa: PLC0415
    from tests.conftest import _make_statement  # noqa: PLC0415

    test_case = tc.TestCase()
    test_case.add_statement(_make_statement("int_0 = 3360", bound_variable="int_0", bound_type=int))
    test_case.add_statement(_make_statement("plus_0 = plus_.Plus()", bound_variable="plus_0"))
    test_case.add_statement(
        _make_statement("var_0 = undefined_name", bound_variable="var_0", bound_type=int)
    )

    config.configuration.module_name = module_name
    config.configuration.search_algorithm.coverage_metrics = [config.CoverageMetric.CHECKED]

    with install_import_hook(module_name, subject_properties):
        with subject_properties.instrumentation_tracer:
            module = importlib.import_module(module_name)
            importlib.reload(module)

        executor = TestCaseExecutor(subject_properties)
        executor.set_instrument(True)
        executor.add_remote_observer(RemoteAssertionExecutionObserver())
        result = executor.execute(test_case)

        assert result.has_test_exceptions()
        assert not result.execution_trace.executed_assertions


def _execute_without_traced_to_bool(test_case, subject_properties, monkeypatch):
    # Treating the traced TO_BOOL as untraced made the backward walk return the same
    # state forever (#336).
    monkeypatch.setattr(
        efb,
        "TRACED_NAMES",
        tuple(name for name in efb.TRACED_NAMES if name != "TO_BOOL"),
    )
    module_name = "tests.fixtures.linecoverage.plus"
    config.configuration.module_name = module_name
    config.configuration.search_algorithm.coverage_metrics = [config.CoverageMetric.CHECKED]

    with install_import_hook(module_name, subject_properties):
        with subject_properties.instrumentation_tracer:
            module = importlib.import_module(module_name)
            importlib.reload(module)

        executor = TestCaseExecutor(subject_properties)
        executor.set_instrument(True)
        executor.add_remote_observer(RemoteAssertionExecutionObserver())
        return executor.execute(test_case)


@pytest.mark.skipif(sys.version_info < (3, 13), reason="TO_BOOL exists since Python 3.13")
def test_slicing_without_progress_fails_instead_of_hanging(
    plus_test_with_isinstance_assertion, subject_properties: SubjectProperties, monkeypatch
):
    result = _execute_without_traced_to_bool(
        plus_test_with_isinstance_assertion, subject_properties, monkeypatch
    )

    assertion_slicer = AssertionSlicer(subject_properties.existing_code_objects)
    (assertion,) = result.execution_trace.executed_assertions
    with pytest.raises(RuntimeError, match="made no progress at <UniqueInstruction TO_BOOL"):
        assertion_slicer.slice_assertion(assertion, result.execution_trace)


@pytest.mark.skipif(sys.version_info < (3, 13), reason="TO_BOOL exists since Python 3.13")
def test_failed_assertion_slice_checks_no_lines(
    plus_test_with_isinstance_assertion,
    subject_properties: SubjectProperties,
    monkeypatch,
    caplog,
):
    result = _execute_without_traced_to_bool(
        plus_test_with_isinstance_assertion, subject_properties, monkeypatch
    )

    checked_lines = compute_assertion_checked_lines(result.execution_trace, subject_properties)

    assert checked_lines == set()
    assert "Failed to slice assertion" in caplog.text


def _walk_state(trace_position: int, instr_original_index: int) -> efb.InstrState:
    instr = SimpleNamespace(code_object_id=0, node_id=0, instr_original_index=instr_original_index)
    return efb.InstrState(instr=instr, trace_position=trace_position, traced_instr=None)


def test_backward_walk_cycle_at_same_trace_position_fails():
    builder = efb.ExecutionFlowBuilder(MagicMock(), {})
    first, second = _walk_state(5, 1), _walk_state(5, 2)

    builder._check_progress(first, second)
    with pytest.raises(RuntimeError, match="made no progress"):
        builder._check_progress(second, first)


def test_backward_walk_revisit_at_new_trace_position_is_allowed():
    builder = efb.ExecutionFlowBuilder(MagicMock(), {})

    builder._check_progress(_walk_state(6, 1), _walk_state(5, 1))
    builder._check_progress(_walk_state(5, 1), _walk_state(4, 1))
