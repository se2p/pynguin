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
import pynguin.testcase.defaulttestcase as dtc
import pynguin.testcase.statement as stmt
import pynguin.utils.generic.genericaccessibleobject as gao
from pynguin.analyses.types import InferredSignature
from pynguin.instrumentation.instrumentation import CheckedCoverageInstrumentation, InstrumentationTransformer
from pynguin.instrumentation.machinery import install_import_hook
from pynguin.slicer.dynamicslicer import AssertionSlicer
from pynguin.testcase.execution import ExecutionTracer, TestCaseExecutor, AssertionData
from tests.fixtures.linecoverage.plus import Plus


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

    # var_0 = plus0.plus_four(var_0)
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


def get_plus_test_with_direct_assertions() -> tcc.TestCaseChromosome:
    """
    Generated testcase:
        int_0 = 42
        plus_0 = module_0.Plus()
        assert plus_0.plus_four(var_0) == 46
    """
    test_case = _get_default_plus_test()
    plus_four_assertion = ass.ObjectAssertion(test_case.statements[2].ret_val, 46)
    test_case.statements[2].add_assertion(plus_four_assertion)
    return tcc.TestCaseChromosome(test_case=test_case)


def _get_plus_test_with_indirect_assertions() -> tcc.TestCaseChromosome:
    """
    Generated testcase:
        int_0 = 42
        plus_0 = module_0.Plus()
        var_0 = plus_0.plus_four(int_0)
        assert var_0 == pytest.approx(46, rel=0.01, abs=0.01)
    """
    test_case = _get_default_plus_test()
    var_0_assertion = ass.FloatAssertion(test_case.statements[2].ret_val, 46)
    test_case.statements[2].add_assertion(var_0_assertion)
    return tcc.TestCaseChromosome(test_case=test_case)


@pytest.mark.parametrize(
    "module_name, chromosome, expected_lines",
    [
        (
            "tests.fixtures.linecoverage.plus",
            get_plus_test_with_direct_assertions(),
            {9, 16, 18},
        ),
        (
            "tests.fixtures.linecoverage.plus",
            _get_plus_test_with_indirect_assertions(),
            {9, 16, 18},
        ),
    ],
)
def test_slicing_after_test_execution(module_name, chromosome, expected_lines):
    config.configuration.statistics_output.coverage_metrics = [
        config.CoverageMetric.CHECKED
    ]

    tracer = ExecutionTracer()
    tracer.current_thread_identifier = threading.current_thread().ident

    with install_import_hook(module_name, tracer):
        module = importlib.import_module(module_name)
        importlib.reload(module)

        executor = TestCaseExecutor(tracer)
        executor.execute(chromosome.test_case, instrument_test=True)

        trace = tracer.get_trace()
        assertions = trace.assertion_trace.assertions
        assert assertions

        assertion_slicer = AssertionSlicer(
            trace, tracer.get_known_data().existing_code_objects
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


@pytest.mark.parametrize(
    "module_name, expected_assertions, expected_lines",
    [
        ("tests.fixtures.assertion.basic", 1, [16]),
        ("tests.fixtures.assertion.multiple", 3, [16, 17, 18]),
        ("tests.fixtures.assertion.loop", 5, [13, 13, 13, 13, 13]),
    ],
)
def test_assertion_detection_on_module(
    module_name, expected_assertions, expected_lines
):
    trace = _get_assertion_trace_for_module(module_name)

    assert len(trace.assertions) == expected_assertions
    for index in range(expected_assertions):
        assert (
            trace.assertions[index].traced_assertion_pop_jump.lineno
            == expected_lines[index]
        )


@pytest.mark.parametrize(
    "chromosome, expected_assertions",
    [
        (get_plus_test_with_direct_assertions(), 1),
        (_get_plus_test_with_indirect_assertions(), 1),
    ],
)
def test_assertion_detection_on_chromosome(chromosome, expected_assertions):
    config.configuration.statistics_output.coverage_metrics = [
        config.CoverageMetric.CHECKED
    ]
    tracer = ExecutionTracer()
    tracer.current_thread_identifier = threading.current_thread().ident

    executor = TestCaseExecutor(tracer)

    executor.execute(chromosome.test_case, instrument_test=True)
    assertion_trace = tracer.get_trace().assertion_trace
    assert len(assertion_trace.assertions) == expected_assertions


def _get_assertion_trace_for_module(module_name: str) -> AssertionData:
    """Trace a given module name with the CheckedCoverage Instrumentation.
    The traced module must contain a test called test_foo()."""
    module = importlib.import_module(module_name)
    module = importlib.reload(module)

    # Setup
    tracer = ExecutionTracer()
    adapter = CheckedCoverageInstrumentation(tracer)
    transformer = InstrumentationTransformer(tracer, [adapter])

    # Instrument and call module
    module.test_foo.__code__ = transformer.instrument_module(module.test_foo.__code__)
    tracer.current_thread_identifier = threading.current_thread().ident
    module.test_foo()

    return tracer.get_trace().assertion_trace
