#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import ast
import importlib
import inspect
import threading

from unittest.mock import MagicMock

import pytest

import pynguin.configuration as config
import pynguin.ga.testcasechromosome as tcc
import pynguin.ga.testsuitechromosome as tsc

from pynguin.analyses.constants import EmptyConstantProvider
from pynguin.analyses.module import generate_test_cluster
from pynguin.analyses.seeding import AstToTestCaseTransformer
from pynguin.analyses.typesystem import InferredSignature
from pynguin.ga.computations import TestCaseStatementCheckedCoverageFunction
from pynguin.ga.computations import TestSuiteStatementCheckedCoverageFunction
from pynguin.instrumentation.machinery import install_import_hook
from pynguin.instrumentation.tracer import ExecutionTracer
from pynguin.slicer.dynamicslicer import DynamicSlicer
from pynguin.slicer.statementslicingobserver import RemoteStatementSlicingObserver
from pynguin.testcase.execution import TestCaseExecutor
from pynguin.testcase.statement import MethodStatement
from pynguin.utils.generic.genericaccessibleobject import GenericMethod
from tests.fixtures.linecoverage.setter_getter import SetterGetter


@pytest.fixture
def plus_three_test():
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
    return transformer.testcases[0]


def test_testsuite_statement_checked_coverage_calculation(plus_three_test):
    module_name = "tests.fixtures.linecoverage.plus"
    test_suite = tsc.TestSuiteChromosome()
    test_suite.add_test_case_chromosome(tcc.TestCaseChromosome(test_case=plus_three_test))
    config.configuration.statistics_output.coverage_metrics = [
        config.CoverageMetric.CHECKED,
    ]

    tracer = ExecutionTracer()
    tracer.current_thread_identifier = threading.current_thread().ident

    with install_import_hook(module_name, tracer):
        module = importlib.import_module(module_name)
        importlib.reload(module)

        executor = TestCaseExecutor(tracer)
        executor.add_remote_observer(RemoteStatementSlicingObserver())

        ff = TestSuiteStatementCheckedCoverageFunction(executor)
        assert ff.compute_coverage(test_suite) == pytest.approx(4 / 8, 0.1, 0.1)


def test_testcase_statement_checked_coverage_calculation(plus_three_test):
    module_name = "tests.fixtures.linecoverage.plus"
    test_case_chromosome = tcc.TestCaseChromosome(test_case=plus_three_test)
    config.configuration.statistics_output.coverage_metrics = [
        config.CoverageMetric.CHECKED,
    ]

    tracer = ExecutionTracer()
    tracer.current_thread_identifier = threading.current_thread().ident

    with install_import_hook(module_name, tracer):
        module = importlib.import_module(module_name)
        importlib.reload(module)

        executor = TestCaseExecutor(tracer)
        executor.add_remote_observer(RemoteStatementSlicingObserver())

        ff = TestCaseStatementCheckedCoverageFunction(executor)
        assert ff.compute_coverage(test_case_chromosome) == pytest.approx(4 / 8, 0.1, 0.1)


@pytest.fixture
def setter_test():
    cluster = generate_test_cluster("tests.fixtures.linecoverage.setter_getter")
    transformer = AstToTestCaseTransformer(
        cluster,
        False,  # noqa: FBT003
        EmptyConstantProvider(),
    )
    transformer.visit(
        ast.parse(
            """def test_case_0():
    setter_getter_0 = module_0.SetterGetter()
    int_0 = 3360
"""
        )
    )
    tc = transformer.testcases[0]

    # we have to manually add a method call without assign,
    # since the AST Parser would ignore this statement
    # without assigning a new variable
    tc.add_statement(
        MethodStatement(
            tc,
            GenericMethod(
                cluster.type_system.to_type_info(SetterGetter),
                SetterGetter.setter,
                InferredSignature(
                    signature=inspect.signature(SetterGetter.setter),
                    original_parameters={
                        "new_attribute": cluster.type_system.convert_type_hint(int)
                    },
                    original_return_type=cluster.type_system.convert_type_hint(None),
                    type_system=cluster.type_system,
                ),
            ),
            tc.statements[0].ret_val,
            {"new_value": tc.statements[1].ret_val},
        )
    )
    return tc


def test_only_void_function(setter_test):
    module_name = "tests.fixtures.linecoverage.setter_getter"
    test_case_chromosome = tcc.TestCaseChromosome(test_case=setter_test)
    config.configuration.statistics_output.coverage_metrics = [
        config.CoverageMetric.CHECKED,
    ]

    tracer = ExecutionTracer()
    tracer.current_thread_identifier = threading.current_thread().ident

    with install_import_hook(module_name, tracer):
        module = importlib.import_module(module_name)
        importlib.reload(module)

        executor = TestCaseExecutor(tracer)
        executor.add_remote_observer(RemoteStatementSlicingObserver())

        ff = TestCaseStatementCheckedCoverageFunction(executor)
        assert ff.compute_coverage(test_case_chromosome) == pytest.approx(3 / 6, 0.1, 0.1)


@pytest.fixture
def getter_setter_test():
    cluster = generate_test_cluster("tests.fixtures.linecoverage.setter_getter")
    transformer = AstToTestCaseTransformer(
        cluster,
        False,  # noqa: FBT003
        EmptyConstantProvider(),
    )
    transformer.visit(
        ast.parse(
            """def test_case_0():
    setter_getter_0 = module_0.SetterGetter()
    int_0 = 3360
    int_1 = setter_getter_0.getter()
"""
        )
    )
    tc = transformer.testcases[0]

    # we have to manually add a method call without assign,
    # since the AST Parser would ignore this statement
    # without assigning a new variable
    tc.add_statement(
        MethodStatement(
            tc,
            GenericMethod(
                cluster.type_system.to_type_info(SetterGetter),
                SetterGetter.setter,
                InferredSignature(
                    signature=inspect.signature(SetterGetter.setter),
                    original_parameters={
                        "new_attribute": cluster.type_system.convert_type_hint(int)
                    },
                    original_return_type=cluster.type_system.convert_type_hint(None),
                    type_system=cluster.type_system,
                ),
            ),
            tc.statements[0].ret_val,
            {"new_value": tc.statements[1].ret_val},
        )
    )
    return tc


def test_getter_before_setter(getter_setter_test):
    module_name = "tests.fixtures.linecoverage.setter_getter"
    test_case_chromosome = tcc.TestCaseChromosome(test_case=getter_setter_test)
    config.configuration.statistics_output.coverage_metrics = [
        config.CoverageMetric.CHECKED,
    ]

    tracer = ExecutionTracer()
    tracer.current_thread_identifier = threading.current_thread().ident

    with install_import_hook(module_name, tracer):
        module = importlib.import_module(module_name)
        importlib.reload(module)

        executor = TestCaseExecutor(tracer)
        executor.add_remote_observer(RemoteStatementSlicingObserver())

        ff = TestCaseStatementCheckedCoverageFunction(executor)
        assert ff.compute_coverage(test_case_chromosome) == pytest.approx(5 / 6, 0.1, 0.1)


@pytest.fixture
def setter_getter_test():
    cluster = generate_test_cluster("tests.fixtures.linecoverage.setter_getter")
    transformer = AstToTestCaseTransformer(
        cluster,
        False,  # noqa: FBT003
        EmptyConstantProvider(),
    )
    transformer.visit(
        ast.parse(
            """def test_case_0():
    setter_getter_0 = module_0.SetterGetter()
    int_0 = 3360
"""
        )
    )
    tc = transformer.testcases[0]

    # we have to manually add a method call without assign,
    # since the AST Parser would ignore this statement
    # without assigning a new variable
    tc.add_statement(
        MethodStatement(
            tc,
            GenericMethod(
                cluster.type_system.to_type_info(SetterGetter),
                SetterGetter.setter,
                InferredSignature(
                    signature=inspect.signature(SetterGetter.setter),
                    original_parameters={
                        "new_attribute": cluster.type_system.convert_type_hint(int)
                    },
                    original_return_type=cluster.type_system.convert_type_hint(None),
                    type_system=cluster.type_system,
                ),
            ),
            tc.statements[0].ret_val,
            {"new_value": tc.statements[1].ret_val},
        )
    )

    tc.add_statement(
        MethodStatement(
            tc,
            GenericMethod(
                cluster.type_system.to_type_info(SetterGetter),
                SetterGetter.getter,
                InferredSignature(
                    signature=inspect.signature(SetterGetter.getter),
                    original_parameters={},
                    original_return_type=cluster.type_system.convert_type_hint(int),
                    type_system=cluster.type_system,
                ),
            ),
            tc.statements[0].ret_val,
        )
    )
    return tc


def test_getter_after_setter(setter_getter_test):
    module_name = "tests.fixtures.linecoverage.setter_getter"
    test_case_chromosome = tcc.TestCaseChromosome(test_case=setter_getter_test)
    config.configuration.statistics_output.coverage_metrics = [
        config.CoverageMetric.CHECKED,
    ]

    tracer = ExecutionTracer()
    tracer.current_thread_identifier = threading.current_thread().ident

    with install_import_hook(module_name, tracer):
        module = importlib.import_module(module_name)
        importlib.reload(module)

        executor = TestCaseExecutor(tracer)
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
