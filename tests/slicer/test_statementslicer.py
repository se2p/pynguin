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

import pynguin.configuration as config
import pynguin.ga.testcasechromosome as tcc
import pynguin.ga.testsuitechromosome as tsc
from pynguin.analyses.constants import EmptyConstantProvider
from pynguin.analyses.module import generate_test_cluster
from pynguin.analyses.seeding import AstToTestCaseTransformer
from pynguin.ga.computations import (
    TestCaseStatementCheckedCoverageFunction,
    TestSuiteStatementCheckedCoverageFunction,
)
from pynguin.instrumentation.machinery import install_import_hook
from pynguin.testcase.execution import ExecutionTracer, TestCaseExecutor


@pytest.fixture
def plus_three_test():
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
    return transformer.testcases[0]


def test_testsuite_statement_checked_coverage_calculation(plus_three_test):
    module_name = "tests.fixtures.linecoverage.plus"
    test_suite = tsc.TestSuiteChromosome()
    test_suite.add_test_case_chromosome(
        tcc.TestCaseChromosome(test_case=plus_three_test)
    )
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

        ff = TestSuiteStatementCheckedCoverageFunction(executor)
        assert ff.compute_coverage(test_suite) == pytest.approx(4 / 8, 0.1, 0.1)


def test_testcase_statement_checked_coverage_calculation(plus_three_test):
    module_name = "tests.fixtures.linecoverage.plus"
    test_case_chromosome = tcc.TestCaseChromosome(test_case=plus_three_test)
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

        ff = TestCaseStatementCheckedCoverageFunction(executor)
        assert ff.compute_coverage(test_case_chromosome) == pytest.approx(
            4 / 8, 0.1, 0.1
        )
