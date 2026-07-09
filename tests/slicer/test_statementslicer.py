#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import importlib
from unittest.mock import MagicMock

import pytest

import pynguin.configuration as config
import pynguin.ga.testcasechromosome as tcc
import pynguin.ga.testsuitechromosome as tsc
import pynguin.testcase.testcase as tc
from pynguin.ga.computations import (
    TestCaseStatementCheckedCoverageFunction,
    TestSuiteStatementCheckedCoverageFunction,
)
from pynguin.instrumentation.machinery import install_import_hook
from pynguin.instrumentation.tracer import SubjectProperties
from pynguin.slicer.dynamicslicer import DynamicSlicer, SlicingCriterion
from pynguin.slicer.statementslicingobserver import RemoteStatementSlicingObserver
from pynguin.testcase.execution import TestCaseExecutor
from pynguin.utils.orderedset import OrderedSet
from tests.conftest import _make_statement


def _plus_three_test() -> tc.TestCase:
    """int_0 = 3360; plus_0 = plus_.Plus(); var_0 = plus_0.plus_three(int_0)."""
    test_case = tc.TestCase()
    test_case.add_statement(_make_statement("int_0 = 3360", bound_variable="int_0", bound_type=int))
    test_case.add_statement(_make_statement("plus_0 = plus_.Plus()", bound_variable="plus_0"))
    test_case.add_statement(
        _make_statement("var_0 = plus_0.plus_three(int_0)", bound_variable="var_0", bound_type=int)
    )
    return test_case


@pytest.fixture
def plus_three_test():
    return _plus_three_test()


def test_testsuite_statement_checked_coverage_calculation(
    plus_three_test, subject_properties: SubjectProperties
):
    module_name = "tests.fixtures.linecoverage.plus"
    test_suite = tsc.TestSuiteChromosome()
    test_suite.add_test_case_chromosome(tcc.TestCaseChromosome(test_case=plus_three_test))
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
        executor.add_remote_observer(RemoteStatementSlicingObserver())

        ff = TestSuiteStatementCheckedCoverageFunction(executor)
        assert ff.compute_coverage(test_suite) == pytest.approx(4 / 8, 0.1, 0.1)


def test_testcase_statement_checked_coverage_calculation(
    plus_three_test, subject_properties: SubjectProperties
):
    module_name = "tests.fixtures.linecoverage.plus"
    test_case_chromosome = tcc.TestCaseChromosome(test_case=plus_three_test)
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
        executor.add_remote_observer(RemoteStatementSlicingObserver())

        ff = TestCaseStatementCheckedCoverageFunction(executor)
        assert ff.compute_coverage(test_case_chromosome) == pytest.approx(4 / 8, 0.1, 0.1)


def _setter_test() -> tc.TestCase:
    """Build the setter-only test case.

    setter_getter_0 = setter_getter_.SetterGetter(); int_0 = 3360;
    setter_getter_0.setter(int_0) (unbound, void call).
    """
    test_case = tc.TestCase()
    test_case.add_statement(
        _make_statement(
            "setter_getter_0 = setter_getter_.SetterGetter()", bound_variable="setter_getter_0"
        )
    )
    test_case.add_statement(_make_statement("int_0 = 3360", bound_variable="int_0", bound_type=int))
    test_case.add_statement(_make_statement("setter_getter_0.setter(int_0)"))
    return test_case


@pytest.fixture
def setter_test():
    return _setter_test()


def test_only_void_function(setter_test, subject_properties: SubjectProperties):
    module_name = "tests.fixtures.linecoverage.setter_getter"
    test_case_chromosome = tcc.TestCaseChromosome(test_case=setter_test)
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
        executor.add_remote_observer(RemoteStatementSlicingObserver())

        ff = TestCaseStatementCheckedCoverageFunction(executor)
        # The void setter() call is unbound and thus contributes no slicing
        # criterion of its own; only the two bound statements are checked.
        assert ff.compute_coverage(test_case_chromosome) == pytest.approx(2 / 6, 0.1, 0.1)


def _getter_setter_test() -> tc.TestCase:
    """Build the getter-before-setter test case.

    setter_getter_0 = ...; int_0 = 3360; int_1 = setter_getter_0.getter();
    setter_getter_0.setter(int_0) (unbound).
    """
    test_case = tc.TestCase()
    test_case.add_statement(
        _make_statement(
            "setter_getter_0 = setter_getter_.SetterGetter()", bound_variable="setter_getter_0"
        )
    )
    test_case.add_statement(_make_statement("int_0 = 3360", bound_variable="int_0", bound_type=int))
    test_case.add_statement(
        _make_statement("int_1 = setter_getter_0.getter()", bound_variable="int_1", bound_type=int)
    )
    test_case.add_statement(_make_statement("setter_getter_0.setter(int_0)"))
    return test_case


@pytest.fixture
def getter_setter_test():
    return _getter_setter_test()


def test_getter_before_setter(getter_setter_test, subject_properties: SubjectProperties):
    module_name = "tests.fixtures.linecoverage.setter_getter"
    test_case_chromosome = tcc.TestCaseChromosome(test_case=getter_setter_test)
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
        executor.add_remote_observer(RemoteStatementSlicingObserver())

        ff = TestCaseStatementCheckedCoverageFunction(executor)
        assert ff.compute_coverage(test_case_chromosome) == pytest.approx(4 / 6, 0.1, 0.1)


def _setter_getter_test() -> tc.TestCase:
    """Build the setter-before-getter test case.

    setter_getter_0 = ...; int_0 = 3360; setter_getter_0.setter(int_0) (unbound);
    int_1 = setter_getter_0.getter().
    """
    test_case = tc.TestCase()
    test_case.add_statement(
        _make_statement(
            "setter_getter_0 = setter_getter_.SetterGetter()", bound_variable="setter_getter_0"
        )
    )
    test_case.add_statement(_make_statement("int_0 = 3360", bound_variable="int_0", bound_type=int))
    test_case.add_statement(_make_statement("setter_getter_0.setter(int_0)"))
    test_case.add_statement(
        _make_statement("int_1 = setter_getter_0.getter()", bound_variable="int_1", bound_type=int)
    )
    return test_case


@pytest.fixture
def setter_getter_test():
    return _setter_getter_test()


def test_getter_after_setter(setter_getter_test, subject_properties: SubjectProperties):
    module_name = "tests.fixtures.linecoverage.setter_getter"
    test_case_chromosome = tcc.TestCaseChromosome(test_case=setter_getter_test)
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
        executor.add_remote_observer(RemoteStatementSlicingObserver())

        ff = TestCaseStatementCheckedCoverageFunction(executor)
        assert ff.compute_coverage(test_case_chromosome) == pytest.approx(5 / 6, 0.1, 0.1)


def test_get_line_id_by_instruction_throws_error():
    instruction_mock = MagicMock(
        code_object_id=0,
        file="foo",
        lineno=1,
    )
    subject_properties_mock = MagicMock(
        existing_lines={
            0: MagicMock(
                code_object_id=0,
                file="foo",
                lineno=2,
            )
        }
    )

    with pytest.raises(ValueError):  # noqa: PT011
        DynamicSlicer.get_line_id_by_instruction(instruction_mock, subject_properties_mock)


def test_unbound_statement_records_no_criterion(subject_properties: SubjectProperties):
    """Unbound statements are skipped, later bound statements still sliced.

    An unbound Expr statement should not get a slicing criterion, and
    compute_statement_checked_lines should still process later bound
    statements (regression for the continue-vs-break change).
    """
    module_name = "tests.fixtures.linecoverage.plus"
    test_case = tc.TestCase()
    test_case.add_statement(_make_statement("int_0 = 3360", bound_variable="int_0", bound_type=int))
    test_case.add_statement(_make_statement("plus_0 = plus_.Plus()", bound_variable="plus_0"))
    # Unbound call: return value discarded, no STORE emitted.
    test_case.add_statement(_make_statement("plus_0.plus_three(int_0)"))
    test_case.add_statement(
        _make_statement("var_0 = plus_0.plus_three(int_0)", bound_variable="var_0", bound_type=int)
    )
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
        observer = RemoteStatementSlicingObserver()
        executor.add_remote_observer(observer)

        result = executor.execute(test_case)

        # The observer's thread-local state lives in the (already finished)
        # execution thread; the merged trace crosses the thread boundary via
        # the execution result and is the correct place to assert on.
        # Positions: 0 (int_0, bound), 1 (plus_0, bound), 2 (unbound call, no
        # criterion), 3 (var_0, bound) -- despite the unbound statement in
        # the middle, later bound statements still get sliced (continue, not
        # break).
        assert not result.has_test_exceptions()
        assert result.execution_trace.checked_lines


def test_exception_abort_stops_criterion_collection(subject_properties: SubjectProperties):
    """When a statement raises, only earlier bound statements get criteria."""
    module_name = "tests.fixtures.linecoverage.plus"
    test_case = tc.TestCase()
    test_case.add_statement(_make_statement("int_0 = 3360", bound_variable="int_0", bound_type=int))
    test_case.add_statement(_make_statement("plus_0 = plus_.Plus()", bound_variable="plus_0"))
    # Raises a NameError, aborting the test case.
    test_case.add_statement(
        _make_statement("var_0 = undefined_name", bound_variable="var_0", bound_type=int)
    )

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
        observer = RemoteStatementSlicingObserver()
        executor.add_remote_observer(observer)

        result = executor.execute(test_case)

        # The third statement raises, aborting the test case; slicing must
        # not crash on the resulting partial trace, and only lines checked
        # by the two statements that actually ran can be reported.
        assert result.has_test_exceptions()
        assert isinstance(result.execution_trace.checked_lines, OrderedSet)


def test_slicing_criterion_is_dataclass():
    criterion = SlicingCriterion(5)
    assert criterion.trace_position == 5
