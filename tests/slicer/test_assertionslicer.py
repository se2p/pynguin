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

import pytest

import pynguin.configuration as config
import pynguin.ga.testcasechromosome as tcc
import pynguin.ga.testsuitechromosome as tsc
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
    config.configuration.statistics_output.coverage_metrics = [config.CoverageMetric.CHECKED]

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
        ("tests.fixtures.linecoverage.plus", "plus_test_with_multiple_assertions"),
    ],
)
def test_slicing_after_test_execution(
    module_name, test_case_name, request, subject_properties: SubjectProperties
):
    test_case = request.getfixturevalue(test_case_name)
    config.configuration.module_name = module_name
    config.configuration.statistics_output.coverage_metrics = [config.CoverageMetric.CHECKED]

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
    config.configuration.statistics_output.coverage_metrics = [
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
    config.configuration.statistics_output.coverage_metrics = [config.CoverageMetric.CHECKED]

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
    not produce an ExecutedAssertion (deliberate deviation vs. main, see
    RemoteAssertionExecutionObserver docstring).
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
    config.configuration.statistics_output.coverage_metrics = [config.CoverageMetric.CHECKED]

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
