#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
import ast
import importlib
import threading

import pytest

import pynguin.assertion.assertion as ass
import pynguin.configuration as config
import pynguin.ga.testcasechromosome as tcc
import pynguin.ga.testsuitechromosome as tsc
import pynguin.testcase.defaulttestcase as dtc
import pynguin.utils.generic.genericaccessibleobject as gao
from pynguin.analyses.constants import EmptyConstantProvider
from pynguin.analyses.module import generate_test_cluster
from pynguin.analyses.seeding import AstToTestCaseTransformer
from pynguin.ga.computations import TestSuiteCheckedCoverageFunction
from pynguin.instrumentation.machinery import install_import_hook
from pynguin.slicer.dynamicslicer import AssertionSlicer
from pynguin.testcase.execution import ExecutionTracer, TestCaseExecutor
from pynguin.testcase.testcase import TestCase
from pynguin.testcase.variablereference import FieldReference, StaticFieldReference
from tests.fixtures.linecoverage.list import ListTest
from tests.fixtures.linecoverage.plus import Plus


@pytest.fixture
def full_cover_plus_three_test():
    """
    Produces the following testcase:
        def test_case_0():
            int_0 = 3360
            plus_0 = module_0.Plus()
            assert plus_0.calculations == 0
            var_0 = plus_0.plus_three(int_0)
            assert var_0 == 3363
            assert plus_0.calculations == 1
    """
    cluster = generate_test_cluster("tests.fixtures.linecoverage.plus")
    transformer = AstToTestCaseTransformer(cluster, False, EmptyConstantProvider())
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
                gao.GenericField(Plus, "calculations", int),
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
                gao.GenericField(Plus, "calculations", int),
            ),
            1,
        )
    )
    return test_case


@pytest.fixture
def full_cover_plus_four_test():
    """
    Produces the following testcase:
        def test_case_1():
            int_0 = -3559
            plus_0 = module_0.Plus()
            assert plus_0.calculations == 0
            var_0 = plus_0.plus_four(int_0)
            assert var_0 == -3555
            assert plus_0.calculations == 1
    """

    cluster = generate_test_cluster("tests.fixtures.linecoverage.plus")
    transformer = AstToTestCaseTransformer(cluster, False, EmptyConstantProvider())
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
                gao.GenericField(Plus, "calculations", int),
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
                gao.GenericField(Plus, "calculations", int),
            ),
            1,
        )
    )
    return test_case


@pytest.fixture
def plus_test_with_float_assertion() -> TestCase:
    """
    Generated testcase:
        int_0 = 42
        plus_0 = module_0.Plus()
        int_1 = plus_0.plus_four(int_0)
        assert int_1 == pytest.approx(46, rel=0.01, abs=0.01)
    """
    cluster = generate_test_cluster("tests.fixtures.linecoverage.plus")
    transformer = AstToTestCaseTransformer(cluster, False, EmptyConstantProvider())
    transformer.visit(
        ast.parse(
            """def test_case_0():
    int_0 = 42
    plus_0 = module_0.Plus()
    int_1 = plus_0.plus_four(int_0)
"""
        )
    )
    test_case = transformer.testcases[0]
    test_case.statements[-1].add_assertion(
        ass.FloatAssertion(test_case.statements[-1].ret_val, 46)
    )
    return test_case


@pytest.fixture
def plus_test_with_not_none_assertion() -> TestCase:
    """
    Generated testcase:
        int_0 = 42
        plus_0 = module_0.Plus()
        int_1 = plus_0.plus_four(int_0)
        assert int_1 is not None
    """
    cluster = generate_test_cluster("tests.fixtures.linecoverage.plus")
    transformer = AstToTestCaseTransformer(cluster, False, EmptyConstantProvider())
    transformer.visit(
        ast.parse(
            """def test_case_0():
    int_0 = 42
    plus_0 = module_0.Plus()
    int_1 = plus_0.plus_four(int_0)
"""
        )
    )
    test_case = transformer.testcases[0]

    test_case.statements[-1].add_assertion(
        ass.NotNoneAssertion(test_case.statements[-1].ret_val)
    )
    return test_case


@pytest.fixture
def exception_test_with_except_assertion() -> TestCase:
    """
    Generated testcase:
        exception_test_0 = module_0.ExceptionTest()
        with pytest.raises(RuntimeError):
            var_0 = exception_test_0.throw()
    """
    cluster = generate_test_cluster("tests.fixtures.linecoverage.exception")
    transformer = AstToTestCaseTransformer(cluster, False, EmptyConstantProvider())
    transformer.visit(
        ast.parse(
            """def test_case_0():
    exception_test_0 = module_0.ExceptionTest()
    var_0 = exception_test_0.throw()
"""
        )
    )
    test_case = transformer.testcases[0]

    test_case.statements[-1].add_assertion(
        ass.ExceptionAssertion(
            module=RuntimeError.__module__,
            exception_type_name=RuntimeError.__name__,
        ),
    )
    return test_case


@pytest.fixture
def list_test_with_len_assertion() -> TestCase:
    """
    Generated testcase:
        list_test_0 = module_0.ListTest()
        assert len(list_test_0.attribute) == 3
    """
    cluster = generate_test_cluster("tests.fixtures.linecoverage.list")
    transformer = AstToTestCaseTransformer(cluster, False, EmptyConstantProvider())
    transformer.visit(
        ast.parse(
            """def test_case_0():
    list_test_0 = module_0.ListTest()
"""
        )
    )
    test_case = transformer.testcases[0]
    test_case.statements[-1].add_assertion(
        ass.CollectionLengthAssertion(
            FieldReference(
                test_case.statements[-1].ret_val,
                gao.GenericField(ListTest, "attribute", list),
            ),
            3,
        )
    )
    return test_case


@pytest.fixture
def plus_test_with_multiple_assertions():
    """
    Generated testcase:
        int_0 = 42
        assert int_0 == 42
        plus_0 = module_0.Plus()
        int_1 = plus_0.plus_four(int_0)
        assert int_1 == pytest.approx(46, rel=0.01, abs=0.01)
        assert plus_0.calculations == 1
    """
    cluster = generate_test_cluster("tests.fixtures.linecoverage.plus")
    transformer = AstToTestCaseTransformer(cluster, False, EmptyConstantProvider())
    transformer.visit(
        ast.parse(
            """def test_case_0():
    int_0 = 42
    plus_0 = module_0.Plus()
    int_1 = plus_0.plus_four(int_0)
"""
        )
    )
    test_case = transformer.testcases[0]

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


@pytest.fixture
def partial_cover_use_bool_as_int():
    cluster = generate_test_cluster("tests.fixtures.linecoverage.plus")
    transformer = AstToTestCaseTransformer(cluster, False, EmptyConstantProvider())
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
                gao.GenericStaticField(Plus, "calculations", int),
            ),
            0,
        )
    )
    tc_0.statements[2].add_assertion(ass.ObjectAssertion(tc_0.statements[2].ret_val, 4))
    tc_0.statements[2].add_assertion(
        ass.ObjectAssertion(
            FieldReference(
                tc_0.statements[1].ret_val,
                gao.GenericField(Plus, "calculations", int),
            ),
            1,
        )
    )

    tc_1 = transformer.testcases[1]
    tc_1.statements[1].add_assertion(
        ass.ObjectAssertion(
            StaticFieldReference(
                gao.GenericStaticField(Plus, "calculations", int),
            ),
            0,
        )
    )
    tc_1.statements[2].add_assertion(
        ass.ObjectAssertion(tc_1.statements[2].ret_val, 1004)
    )

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
def no_cover_plus_testsuite() -> tsc.TestSuiteChromosome:
    test_suite = tsc.TestSuiteChromosome()
    test_suite.add_test_case_chromosome(tcc.TestCaseChromosome(dtc.DefaultTestCase()))
    return test_suite


@pytest.mark.parametrize(
    "test_case_name, expected_assertions",
    [
        ("plus_test_with_object_assertion", 1),
        ("plus_test_with_float_assertion", 1),
        ("plus_test_with_not_none_assertion", 1),
        ("exception_test_with_except_assertion", 1),
        ("list_test_with_len_assertion", 1),
        ("plus_test_with_multiple_assertions", 3),
    ],
)
def test_assertion_detection_on_test_case(test_case_name, expected_assertions, request):
    test_case = request.getfixturevalue(test_case_name)
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
    "module_name, test_case_name, expected_lines",
    [
        (
            "tests.fixtures.linecoverage.plus",
            "plus_test_with_object_assertion",
            {9, 16, 18},
        ),
        (
            "tests.fixtures.linecoverage.plus",
            "plus_test_with_float_assertion",
            {9, 16, 18},
        ),
        (
            "tests.fixtures.linecoverage.plus",
            "plus_test_with_multiple_assertions",
            {9, 10, 16, 17, 18},
        ),
    ],
)
def test_slicing_after_test_execution(
    module_name, test_case_name, expected_lines, request
):
    test_case = request.getfixturevalue(test_case_name)
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
            "full_cover_plus_testsuite",
            1,
        ),
        (
            "tests.fixtures.linecoverage.plus",
            "partial_cover_use_bool_as_int",
            # covers all but one line
            7 / 8,
        ),
    ],
)
def test_testsuite_checked_execution_and_calculation(
    module_name, test_suite_name, expected_coverage, request
):
    test_suite = request.getfixturevalue(test_suite_name)
    config.configuration.statistics_output.coverage_metrics = [
        config.CoverageMetric.LINE,
        config.CoverageMetric.CHECKED,
    ]

    tracer = ExecutionTracer()
    tracer.current_thread_identifier = threading.current_thread().ident

    with install_import_hook(module_name, tracer):
        module = importlib.import_module(module_name)
        importlib.reload(module)

        executor = TestCaseExecutor(tracer)

        ff = TestSuiteCheckedCoverageFunction(executor)
        assert ff.compute_coverage(test_suite) == pytest.approx(
            expected_coverage, 0.1, 0.1
        )
