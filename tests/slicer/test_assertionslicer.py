#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
import importlib
import inspect
import threading

import pynguin.assertion.assertion as ass
import pynguin.configuration as config
import pynguin.ga.testcasechromosome as tcc
import pynguin.testcase.defaulttestcase as dtc
import pynguin.testcase.statement as stmt
import pynguin.utils.generic.genericaccessibleobject as gao
from pynguin.analyses.types import InferredSignature
from pynguin.instrumentation.machinery import install_import_hook
from pynguin.slicer.dynamicslicer import AssertionSlicer
from pynguin.testcase.execution import ExecutionTracer, TestCaseExecutor
from tests.fixtures.linecoverage.plus import Plus


def test_slicing_after_test_execution():
    module_name = "tests.fixtures.linecoverage.plus"
    config.configuration.statistics_output.coverage_metrics = [
        config.CoverageMetric.CHECKED
    ]

    expected_lines = {9, 16, 18}

    tracer = ExecutionTracer()
    tracer.current_thread_identifier = threading.current_thread().ident

    with install_import_hook(module_name, tracer):
        module = importlib.import_module(module_name)
        importlib.reload(module)

        executor = TestCaseExecutor(tracer)
        chromosome = get_plus_test_with_assertions()

        executor.execute(chromosome.test_case, instrument_test=True)
        trace = tracer.get_trace()
        assertions = trace.assertion_trace.assertions
        assert assertions

        assertion_slicer = AssertionSlicer(
            trace, tracer.get_known_data().existing_code_objects
        )

        instructions_in_slice = []
        for assertion in assertions:
            instructions_checked_by_assertion = assertion_slicer.slice_assertion(
                assertion
            )
            instructions_in_slice.extend(instructions_checked_by_assertion)

        assert instructions_in_slice

        checked_lines = assertion_slicer.map_instructions_to_lines(
            instructions_in_slice
        )
        assert checked_lines
        assert checked_lines == expected_lines


def get_plus_test_with_assertions() -> tcc.TestCaseChromosome:
    """
    Generated testcase:
        var_0 = 42
        var_1 = module_0.Plus()
        assert var_1.plus_four(var_0) == 46
    """
    test_case = dtc.DefaultTestCase()

    # var_0 = 42
    int_stmt = stmt.IntPrimitiveStatement(test_case, 42)

    # var_1 = module_0.Plus()
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

    # assert var_1.plus_four(var_0) == 46
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
    plus_four_assertion = ass.ObjectAssertion(method_call.ret_val, 46)
    method_call.add_assertion(plus_four_assertion)

    test_case.add_statement(int_stmt)
    test_case.add_statement(constructor_call)
    test_case.add_statement(method_call)

    return tcc.TestCaseChromosome(test_case=test_case)
