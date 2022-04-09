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
from pynguin.slicer.assertionslicer import AssertionSlicer
from pynguin.testcase.execution import ExecutionTracer, TestCaseExecutor
from pynguin.testcase.variablereference import FieldReference
from tests.fixtures.linecoverage.plus import Plus


def test_slicing_after_test_execution():
    module_name = "tests.fixtures.linecoverage.plus"
    config.configuration.statistics_output.coverage_metrics = [
        config.CoverageMetric.CHECKED
    ]
    tracer = ExecutionTracer()
    tracer.current_thread_identifier = threading.current_thread().ident

    with install_import_hook(module_name, tracer):
        module = importlib.import_module(module_name)
        importlib.reload(module)

        executor = TestCaseExecutor(tracer)
        chromosome = get_plus_test_with_assertions()

        executor.execute(chromosome.test_case)

        assertion_slicer = AssertionSlicer(tracer)

        instruction_in_slice = []
        for assertion in chromosome.test_case.get_assertions():
            instruction_in_slice.extend(assertion_slicer.slice_assertion(assertion))

        # TODO(SiL) add possibility to map from covered instructions to covered lines
        # TODO(SiL) assert that the correct line os the Plus module were included in the slice


def get_plus_test_with_assertions() -> tcc.TestCaseChromosome:
    """
    Generated testcase:
        number = 42
        plus = Plus()
        assert plus.calculation == 0
        assert plus.plus_four(number) == 46
    """
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

    # assert plus.calculations == 0
    calculation_counter_assertion = ass.ObjectAssertion(
        FieldReference(
            constructor_call.ret_val,
            gao.GenericField(
                Plus,
                "calculations",
                int
            )
        ),
        0
    )
    constructor_call.add_assertion(calculation_counter_assertion)

    # int_1 = plus.plus_four(int_0)
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
    plus_four_assertion = ass.ObjectAssertion(
        method_call.ret_val,
        46
    )
    method_call.add_assertion(plus_four_assertion)

    test_case.add_statement(int_stmt)
    test_case.add_statement(constructor_call)
    test_case.add_statement(method_call)

    return tcc.TestCaseChromosome(test_case=test_case)
