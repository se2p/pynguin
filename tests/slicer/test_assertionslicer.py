#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
import importlib
import inspect
import threading

import pytest

import pynguin.assertion.assertion as ass
import pynguin.configuration as config
import pynguin.ga.testcasechromosome as tcc
import pynguin.ga.testsuitechromosome as tsc
import pynguin.testcase.defaulttestcase as dtc
import pynguin.testcase.statement as stmt
import pynguin.utils.generic.genericaccessibleobject as gao
from pynguin.analyses.types import InferredSignature
from pynguin.ga.computations import TestSuiteCheckedCoverageFunction
from pynguin.instrumentation.machinery import install_import_hook
from pynguin.slicer.dynamicslicer import AssertionSlicer
from pynguin.testcase.execution import ExecutionTracer, TestCaseExecutor
from pynguin.testcase.testcase import TestCase
from pynguin.testcase.variablereference import FieldReference
from tests.fixtures.linecoverage.plus import Plus


class ListTest:
    attribute = [1, 2, 3]


class ExceptionTest:
    def throw(self):
        raise RuntimeError


def _get_default_plus_test():
    test_case = dtc.DefaultTestCase()

    # int_0 = 42
    int_stmt = stmt.IntPrimitiveStatement(test_case, 42)

    # plus_0 = module_0.Plus()
    constructor_call = stmt.ConstructorStatement(
        test_case,
        gao.GenericConstructor(
            Plus,
            InferredSignature(
                signature=inspect.signature(Plus.__init__),
                parameters={},
                return_type=Plus,
            ),
        ),
    )

    # int_1 = plus0.plus_four(var_0)
    method_call = stmt.MethodStatement(
        test_case,
        gao.GenericMethod(
            Plus,
            Plus.plus_four,
            InferredSignature(
                signature=inspect.signature(Plus.plus_four),
                parameters={"number": int},
                return_type=int,
            ),
        ),
        constructor_call.ret_val,
        {"number": int_stmt.ret_val},
    )

    test_case.add_statement(int_stmt)
    test_case.add_statement(constructor_call)
    test_case.add_statement(method_call)
    return test_case


def _get_default_list_test():
    test_case = dtc.DefaultTestCase()

    # listtest_0 = module_0.ListTest()
    constructor_call = stmt.ConstructorStatement(
        test_case,
        gao.GenericConstructor(
            ListTest,
            InferredSignature(
                signature=inspect.signature(ListTest.__init__),
                parameters={},
                return_type=ListTest,
            ),
        ),
    )

    # attribute_0 = listtest_0.attribute
    list_attribute_call = stmt.FieldStatement(
        test_case,
        gao.GenericField(owner=ListTest, field="attribute", field_type=list),
        constructor_call.ret_val,
    )

    test_case.add_statement(constructor_call)
    test_case.add_statement(list_attribute_call)
    return test_case


def _get_default_exception_test() -> TestCase:
    test_case = dtc.DefaultTestCase()

    # exception_test_0 = module_0.ExceptionTest()
    constructor_call = stmt.ConstructorStatement(
        test_case,
        gao.GenericConstructor(
            ExceptionTest,
            InferredSignature(
                signature=inspect.signature(ExceptionTest.__init__),
                parameters={},
                return_type=ExceptionTest,
            ),
        ),
    )

    # exception_test_0.throw()
    method_call = stmt.MethodStatement(
        test_case,
        gao.GenericMethod(
            ExceptionTest,
            ExceptionTest.throw,
            InferredSignature(
                signature=inspect.signature(ExceptionTest.throw),
                parameters={},
                return_type=None,
            ),
        ),
        constructor_call.ret_val,
        {},
    )

    test_case.add_statement(constructor_call)
    test_case.add_statement(method_call)
    return test_case


def get_plus_test_with_object_assertion() -> TestCase:
    """
    Generated testcase:
        int_0 = 42
        plus_0 = module_0.Plus()
        int_1 = plus_0.plus_four(var_0)
        assert int_1 == 46
    """
    test_case = _get_default_plus_test()
    test_case.statements[-1].add_assertion(
        ass.ObjectAssertion(test_case.statements[-1].ret_val, 46)
    )
    return test_case


def _get_plus_test_with_float_assertion() -> TestCase:
    """
    Generated testcase:
        int_0 = 42
        plus_0 = module_0.Plus()
        int_1 = plus_0.plus_four(int_0)
        assert int_1 == pytest.approx(46, rel=0.01, abs=0.01)
    """
    test_case = _get_default_plus_test()
    test_case.statements[-1].add_assertion(
        ass.FloatAssertion(test_case.statements[-1].ret_val, 46)
    )
    return test_case


def _get_plus_test_with_not_none_assertion() -> TestCase:
    """
    Generated testcase:
        int_0 = 42
        plus_0 = module_0.Plus()
        int_1 = plus_0.plus_four(int_0)
        assert int_1 is not None
    """
    test_case = _get_default_plus_test()
    test_case.statements[-1].add_assertion(
        ass.NotNoneAssertion(test_case.statements[-1].ret_val)
    )
    return test_case


def _get_exception_test_with_except_assertion() -> TestCase:
    """
    Generated testcase:
        exception_test_0 = module_0.ExceptionTest()
        with pytest.raises(RuntimeError):
            exception_test_0.throw()
    """
    test_case = _get_default_exception_test()
    test_case.statements[-1].add_assertion(
        ass.ExceptionAssertion(
            module=RuntimeError.__module__,
            exception_type_name=RuntimeError.__name__,
        ),
    )
    return test_case


def _get_list_test_with_len_assertion() -> TestCase:
    """
    Generated testcase:
        list_test_0 = module_0.ListTest()
        list_0 = list_test_0.attribute
        assert len(list_0) == 3
    """
    test_case = _get_default_list_test()
    test_case.statements[-1].add_assertion(
        ass.CollectionLengthAssertion(test_case.statements[-1].ret_val, 3)
    )
    return test_case


def _get_plus_test_with_multiple_assertions():
    """
    Generated testcase:
        int_0 = 42
        assert int_0 == 42
        plus_0 = module_0.Plus()
        int_1 = plus_0.plus_four(int_0)
        assert int_1 == pytest.approx(46, rel=0.01, abs=0.01)
        assert plus_0.calculations == 1
    """
    test_case = _get_default_plus_test()
    test_case.statements[0].add_assertion(
        ass.ObjectAssertion(test_case.statements[0].ret_val, 42)
    )
    test_case.statements[-1].add_assertion(
        ass.FloatAssertion(test_case.statements[-1].ret_val, 46)
    )
    test_case.statements[-1].add_assertion(
        ass.ObjectAssertion(
            FieldReference(
                test_case.statements[1].ret_val,
                gao.GenericField(Plus, "calculations", int),
            ),
            1,
        )
    )
    return test_case


@pytest.mark.parametrize(
    "test_case, expected_assertions",
    [
        (get_plus_test_with_object_assertion(), 1),
        (_get_plus_test_with_float_assertion(), 1),
        (_get_plus_test_with_not_none_assertion(), 1),
        (_get_exception_test_with_except_assertion(), 1),
        (_get_list_test_with_len_assertion(), 1),
        (_get_plus_test_with_multiple_assertions(), 3),
    ],
)
def test_assertion_detection_on_test_case(test_case, expected_assertions):
    config.configuration.statistics_output.coverage_metrics = [
        config.CoverageMetric.CHECKED
    ]
    tracer = ExecutionTracer()
    tracer.current_thread_identifier = threading.current_thread().ident

    executor = TestCaseExecutor(tracer)

    executor.execute(test_case, instrument_test=True)
    assert tracer.get_trace().existing_assertions
    assert len(tracer.get_trace().existing_assertions) == expected_assertions


@pytest.mark.parametrize(
    "module_name, test_case, expected_lines",
    [
        (
            "tests.fixtures.linecoverage.plus",
            get_plus_test_with_object_assertion(),
            {9, 16, 18},
        ),
        (
            "tests.fixtures.linecoverage.plus",
            _get_plus_test_with_float_assertion(),
            {9, 16, 18},
        ),
        (
            "tests.fixtures.linecoverage.plus",
            _get_plus_test_with_multiple_assertions(),
            {9, 10, 16, 17, 18},
        ),
    ],
)
def test_slicing_after_test_execution(module_name, test_case, expected_lines):
    config.configuration.statistics_output.coverage_metrics = [
        config.CoverageMetric.CHECKED
    ]

    tracer = ExecutionTracer()
    tracer.current_thread_identifier = threading.current_thread().ident

    with install_import_hook(module_name, tracer):
        module = importlib.import_module(module_name)
        importlib.reload(module)

        executor = TestCaseExecutor(tracer)
        executor.execute(test_case, instrument_test=True)

        assertions = tracer.get_trace().existing_assertions
        assert assertions
        assertion_slicer = AssertionSlicer(
            tracer.get_trace(), tracer.get_known_data().existing_code_objects
        )
        instructions_in_slice = []
        for assertion in assertions:
            instructions_in_slice.extend(assertion_slicer.slice_assertion(assertion))
        assert instructions_in_slice

        checked_lines = assertion_slicer.map_instructions_to_lines(
            instructions_in_slice
        )
        assert checked_lines
        assert checked_lines == expected_lines


def test_trace_merge_of_multiple_test_cases():
    config.configuration.statistics_output.coverage_metrics = [
        config.CoverageMetric.LINE,
        config.CoverageMetric.CHECKED,
    ]
    test_case_1 = tcc.TestCaseChromosome(_get_plus_test_with_float_assertion())
    test_case_2 = tcc.TestCaseChromosome(_get_plus_test_with_multiple_assertions())
    test_suite = tsc.TestSuiteChromosome()
    test_suite.add_test_case_chromosome(test_case_1)
    test_suite.add_test_case_chromosome(test_case_2)

    tracer = ExecutionTracer()
    tracer.current_thread_identifier = threading.current_thread().ident
    module_name = "tests.fixtures.linecoverage.plus"

    with install_import_hook(module_name, tracer):
        module = importlib.import_module(module_name)
        importlib.reload(module)

        executor = TestCaseExecutor(tracer)

        ff = TestSuiteCheckedCoverageFunction(executor)
        assert ff.compute_coverage(test_suite) == pytest.approx(5 / 8, 0.1, 0.1)
