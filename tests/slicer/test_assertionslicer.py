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
from pynguin.testcase.variablereference import FieldReference
from tests.fixtures.linecoverage.plus import Plus


def test_slicing_after_test_execution():
    module_name = "tests.fixtures.linecoverage.plus"
    config.configuration.statistics_output.coverage_metrics = [
        config.CoverageMetric.CHECKED
    ]

    expected_instructions = []  # TODO(SiL) add expected instr

    tracer = ExecutionTracer()
    tracer.current_thread_identifier = threading.current_thread().ident

    with install_import_hook(module_name, tracer):
        module = importlib.import_module(module_name)
        importlib.reload(module)

        executor = TestCaseExecutor(tracer)
        chromosome = get_plus_test_with_assertions()

        executor.execute(chromosome.test_case, instrument_test=True)

        assert tracer.get_trace().assertion_trace.traced_assertions

        assertion_slicer = AssertionSlicer(
            tracer, tracer.get_known_data().existing_code_objects
        )

        instruction_in_slice = []
        for assertion in tracer.get_trace().assertion_trace.traced_assertions:
            instruction_in_slice.extend(assertion_slicer.slice_assertion(assertion))

        assert len(expected_instructions) == len(instruction_in_slice)
        assert expected_instructions == instruction_in_slice


def get_plus_test_with_assertions() -> tcc.TestCaseChromosome:
    """
    Generated testcase:
        var_0 = 42
        var_1 = module_0.Plus()
        assert var_1.calculation == 0
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

    # assert var_1.calculation == 0
    calculation_counter_assertion = ass.ObjectAssertion(
        FieldReference(
            constructor_call.ret_val, gao.GenericField(Plus, "calculations", int)
        ),
        0,
    )
    constructor_call.add_assertion(calculation_counter_assertion)

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
    # assert int_1 == 46
    plus_four_assertion = ass.ObjectAssertion(method_call.ret_val, 46)
    method_call.add_assertion(plus_four_assertion)

    test_case.add_statement(int_stmt)
    test_case.add_statement(constructor_call)
    test_case.add_statement(method_call)

    return tcc.TestCaseChromosome(test_case=test_case)
