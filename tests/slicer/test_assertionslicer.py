#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import ast
import importlib
import threading

import pytest

import pynguin.assertion.assertion as ass
import pynguin.configuration as config
import pynguin.ga.testcasechromosome as tcc
import pynguin.ga.testsuitechromosome as tsc
import pynguin.utils.generic.genericaccessibleobject as gao

from pynguin.analyses.constants import EmptyConstantProvider
from pynguin.analyses.module import generate_test_cluster
from pynguin.analyses.seeding import AstToTestCaseTransformer
from pynguin.ga.computations import TestSuiteAssertionCheckedCoverageFunction
from pynguin.instrumentation.machinery import install_import_hook
from pynguin.instrumentation.tracer import ExecutionTracer
from pynguin.slicer.dynamicslicer import AssertionSlicer
from pynguin.slicer.dynamicslicer import DynamicSlicer
from pynguin.testcase.execution import RemoteAssertionExecutionObserver
from pynguin.testcase.execution import TestCaseExecutor
from pynguin.testcase.variablereference import FieldReference
from pynguin.testcase.variablereference import StaticFieldReference
from tests.fixtures.linecoverage.plus import Plus


@pytest.fixture
def full_cover_plus_three_test():
    """Produces the following testcase.

    def test_case_0():
        int_0 = 3360
        plus_0 = module_0.Plus()
        assert plus_0.calculations == 0
        var_0 = plus_0.plus_three(int_0)
        assert var_0 == 3363
        assert plus_0.calculations == 1.
    """
    cluster = generate_test_cluster("tests.fixtures.linecoverage.plus")
    transformer = AstToTestCaseTransformer(
        cluster,
        False,  # noqa: FBT003
        EmptyConstantProvider(),
    )
    transformer.visit(
        ast.parse(
            """def test_case_0():
    int_0 = 3360
    plus_0 = module_0.Plus()
    var_0 = plus_0.plus_three(int_0)
"""
        )
    )
    test_case = transformer.testcases[0]
    constructor_call = test_case.statements[1]
    constructor_call.add_assertion(
        ass.ObjectAssertion(
            FieldReference(
                constructor_call.ret_val,
                gao.GenericField(
                    cluster.type_system.to_type_info(Plus),
                    "calculations",
                    cluster.type_system.convert_type_hint(int),
                ),
            ),
            0,
        )
    )
    method_call = test_case.statements[2]
    method_call.add_assertion(ass.ObjectAssertion(method_call.ret_val, 3363))
    method_call.add_assertion(
        ass.ObjectAssertion(
            FieldReference(
                constructor_call.ret_val,
                gao.GenericField(
                    cluster.type_system.to_type_info(Plus),
                    "calculations",
                    cluster.type_system.convert_type_hint(int),
                ),
            ),
            1,
        )
    )
    return test_case


@pytest.fixture
def full_cover_plus_four_test():
    """Produces the following testcase.

    def test_case_1():
        int_0 = -3559
        plus_0 = module_0.Plus()
        assert plus_0.calculations == 0
        var_0 = plus_0.plus_four(int_0)
        assert var_0 == -3555
        assert plus_0.calculations == 1.
    """
    cluster = generate_test_cluster("tests.fixtures.linecoverage.plus")
    transformer = AstToTestCaseTransformer(
        cluster,
        False,  # noqa: FBT003
        EmptyConstantProvider(),
    )
    transformer.visit(
        ast.parse(
            """def test_case_0():
    int_0 = -3559
    plus_0 = module_0.Plus()
    var_0 = plus_0.plus_four(int_0)
"""
        )
    )
    test_case = transformer.testcases[0]
    constructor_call = test_case.statements[1]
    constructor_call.add_assertion(
        ass.ObjectAssertion(
            FieldReference(
                constructor_call.ret_val,
                gao.GenericField(
                    cluster.type_system.to_type_info(Plus),
                    "calculations",
                    cluster.type_system.convert_type_hint(int),
                ),
            ),
            0,
        )
    )
    method_call = test_case.statements[2]
    method_call.add_assertion(ass.ObjectAssertion(method_call.ret_val, -3555))
    method_call.add_assertion(
        ass.ObjectAssertion(
            FieldReference(
                constructor_call.ret_val,
                gao.GenericField(
                    cluster.type_system.to_type_info(Plus),
                    "calculations",
                    cluster.type_system.convert_type_hint(int),
                ),
            ),
            1,
        )
    )
    return test_case


@pytest.fixture
def partial_cover_use_bool_as_int():
    cluster = generate_test_cluster("tests.fixtures.linecoverage.plus")
    transformer = AstToTestCaseTransformer(
        cluster,
        False,  # noqa: FBT003
        EmptyConstantProvider(),
    )
    transformer.visit(
        ast.parse(
            """def test_case_0():
    bool_0 = False
    plus_0 = module_0.Plus()
    var_0 = plus_0.plus_four(bool_0)

def test_case_1():
    int_0 = 1001
    plus_0 = module_0.Plus()
    var_0 = plus_0.plus_three(int_0)
    """
        )
    )

    tc_0 = transformer.testcases[0]
    tc_0.statements[1].add_assertion(
        ass.ObjectAssertion(
            StaticFieldReference(
                gao.GenericStaticField(
                    cluster.type_system.to_type_info(Plus),
                    "calculations",
                    cluster.type_system.convert_type_hint(int),
                ),
            ),
            0,
        )
    )
    tc_0.statements[2].add_assertion(ass.ObjectAssertion(tc_0.statements[2].ret_val, 4))
    tc_0.statements[2].add_assertion(
        ass.ObjectAssertion(
            FieldReference(
                tc_0.statements[1].ret_val,
                gao.GenericField(
                    cluster.type_system.to_type_info(Plus),
                    "calculations",
                    cluster.type_system.convert_type_hint(int),
                ),
            ),
            1,
        )
    )

    tc_1 = transformer.testcases[1]
    tc_1.statements[1].add_assertion(
        ass.ObjectAssertion(
            StaticFieldReference(
                gao.GenericStaticField(
                    cluster.type_system.to_type_info(Plus),
                    "calculations",
                    cluster.type_system.convert_type_hint(int),
                ),
            ),
            0,
        )
    )
    tc_1.statements[2].add_assertion(ass.ObjectAssertion(tc_1.statements[2].ret_val, 1004))

    test_suite = tsc.TestSuiteChromosome()
    test_suite.add_test_case_chromosome(tcc.TestCaseChromosome(tc_0))
    test_suite.add_test_case_chromosome(tcc.TestCaseChromosome(tc_1))
    return test_suite


@pytest.fixture
def full_cover_plus_testsuite(
    full_cover_plus_three_test, full_cover_plus_four_test
) -> tsc.TestSuiteChromosome:
    test_case_1 = tcc.TestCaseChromosome(full_cover_plus_three_test)
    test_case_2 = tcc.TestCaseChromosome(full_cover_plus_four_test)
    test_suite = tsc.TestSuiteChromosome()
    test_suite.add_test_case_chromosome(test_case_1)
    test_suite.add_test_case_chromosome(test_case_2)
    return test_suite


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
    module_name, test_case_name, expected_assertions, request
):
    test_case = request.getfixturevalue(test_case_name)
    config.configuration.statistics_output.coverage_metrics = [config.CoverageMetric.CHECKED]

    tracer = ExecutionTracer()
    tracer.current_thread_identifier = threading.current_thread().ident

    with install_import_hook(module_name, tracer):
        module = importlib.import_module(module_name)
        importlib.reload(module)

        executor = TestCaseExecutor(tracer)
        executor.add_remote_observer(RemoteAssertionExecutionObserver())
        result = executor.execute(test_case)
        assert result.execution_trace.executed_assertions
        assert len(result.execution_trace.executed_assertions) == expected_assertions


@pytest.mark.parametrize(
    "module_name, test_case_name, expected_lines",
    [
        (
            "tests.fixtures.linecoverage.plus",
            "plus_test_with_object_assertion",
            {0, 3, 7},
        ),
        (
            "tests.fixtures.linecoverage.plus",
            "plus_test_with_float_assertion",
            {0, 3, 7},
        ),
        (
            "tests.fixtures.linecoverage.plus",
            "plus_test_with_multiple_assertions",
            {0, 1, 3, 6, 7},
        ),
    ],
)
def test_slicing_after_test_execution(module_name, test_case_name, expected_lines, request):
    test_case = request.getfixturevalue(test_case_name)
    config.configuration.statistics_output.coverage_metrics = [config.CoverageMetric.CHECKED]

    tracer = ExecutionTracer()
    tracer.current_thread_identifier = threading.current_thread().ident

    with install_import_hook(module_name, tracer):
        module = importlib.import_module(module_name)
        importlib.reload(module)

        executor = TestCaseExecutor(tracer)
        executor.add_remote_observer(RemoteAssertionExecutionObserver())
        result = executor.execute(test_case)
        assert result.execution_trace.executed_assertions

        instructions_in_slice = []
        assertion_slicer = AssertionSlicer(tracer.get_subject_properties().existing_code_objects)
        for assertion in result.execution_trace.executed_assertions:
            instructions_in_slice.extend(
                assertion_slicer.slice_assertion(assertion, result.execution_trace)
            )
        assert instructions_in_slice

        checked_lines = DynamicSlicer.map_instructions_to_lines(
            instructions_in_slice, tracer.get_subject_properties()
        )
        assert checked_lines
        assert checked_lines == expected_lines


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
        (
            "tests.fixtures.linecoverage.plus",
            "partial_cover_use_bool_as_int",
            # covers all but one line
            7 / 8,
        ),
        (
            "tests.fixtures.linecoverage.plus",
            "full_cover_plus_testsuite",
            1,
        ),
    ],
)
def test_testsuite_assertion_checked_coverage_calculation(
    module_name, test_suite_name, expected_coverage, request
):
    test_suite = request.getfixturevalue(test_suite_name)
    config.configuration.statistics_output.coverage_metrics = [
        config.CoverageMetric.CHECKED,
    ]

    tracer = ExecutionTracer()
    tracer.current_thread_identifier = threading.current_thread().ident

    with install_import_hook(module_name, tracer):
        module = importlib.import_module(module_name)
        importlib.reload(module)

        executor = TestCaseExecutor(tracer)
        executor.add_remote_observer(RemoteAssertionExecutionObserver())
        ff = TestSuiteAssertionCheckedCoverageFunction(executor)
        assert ff.compute_coverage(test_suite) == pytest.approx(expected_coverage, 0.1, 0.1)
