#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
import ast
import importlib
import threading
from unittest import mock
from unittest.mock import call

import pytest

import pynguin.assertion.assertiongenerator as ag
import pynguin.configuration as config
import pynguin.ga.testcasechromosome as tcc
import pynguin.ga.testsuitechromosome as tsc
import pynguin.testcase.testcase_to_ast as tc_to_ast
import pynguin.utils.namingscope as ns
from pynguin.analyses.constants import EmptyConstantProvider
from pynguin.analyses.module import generate_test_cluster
from pynguin.analyses.seeding import AstToTestCaseTransformer
from pynguin.instrumentation.machinery import install_import_hook
from pynguin.testcase.execution import ExecutionTracer, TestCaseExecutor
from pynguin.utils.statistics.runtimevariable import RuntimeVariable


@pytest.mark.parametrize(
    "generator,expected_result",
    [
        (
            ag.AssertionGenerator,
            """str_0 = 'foo bar'
float_0 = 39.82
human_0 = module_0.Human(str_0, float_0)
assert human_0 is not None
assert module_0.static_state == 0
str_1 = human_0.get_name()
assert str_1 == 'foo bar'""",
        ),
        (
            ag.MutationAnalysisAssertionGenerator,
            """str_0 = 'foo bar'
float_0 = 39.82
human_0 = module_0.Human(str_0, float_0)
assert module_0.static_state == 0
str_1 = human_0.get_name()""",
        ),
    ],
)
def test_generate_mutation_assertions(generator, expected_result):
    config.configuration.module_name = "tests.fixtures.examples.assertions"
    module_name = config.configuration.module_name
    tracer = ExecutionTracer()
    tracer.current_thread_identifier = threading.current_thread().ident
    with install_import_hook(module_name, tracer):
        importlib.reload(importlib.import_module(module_name))
        cluster = generate_test_cluster(module_name)
        transformer = AstToTestCaseTransformer(cluster, False, EmptyConstantProvider())
        transformer.visit(
            ast.parse(
                """def test_case_0():
        str_0 = 'foo bar'
        float_0 = 39.82
        human_0 = module_0.Human(str_0, float_0)
        str_1 = human_0.get_name()
    """
            )
        )
        test_case = transformer.testcases[0]

        chromosome = tcc.TestCaseChromosome(test_case)
        suite = tsc.TestSuiteChromosome()
        suite.add_test_case_chromosome(chromosome)

        gen = generator(TestCaseExecutor(tracer))
        suite.accept(gen)

        visitor = tc_to_ast.TestCaseToAstVisitor(ns.NamingScope(prefix="module"), set())
        test_case.accept(visitor)
        source = ast.unparse(
            ast.fix_missing_locations(
                ast.Module(body=visitor.test_case_ast, type_ignores=[])
            )
        )
        assert source == expected_result


@pytest.mark.parametrize(
    "test_case_str,test_case_str_with_assertions,killed_mut,created_mut,timeout_mut,mut_score",
    [
        pytest.param(
            """def test_case_0():
    int_0 = 1
    float_0 = module_0.foo(int_0)""",
            """int_0 = 1
float_0 = module_0.foo(int_0)
assert float_0 == pytest.approx(3.0, abs=0.01, rel=0.01)""",
            4,
            6,
            0,
            0.6666666666666666,
            id="Kills 0, 1, 4, 5",
        ),
        pytest.param(
            """def test_case_0():
    int_0 = 0
    float_0 = module_0.foo(int_0)""",
            """int_0 = 0
float_0 = module_0.foo(int_0)""",
            0,
            6,
            0,
            0.0,
            id="Kills Nothing as we have no base assertions",
        ),
    ],
)
def test_mutation_score(
    test_case_str,
    test_case_str_with_assertions,
    killed_mut,
    created_mut,
    timeout_mut,
    mut_score,
):
    """
    We have a module tests/fixtures/mutation/mutation.py that looks like this:

    from random import uniform


    def foo(param) -> float:
        '''This is flaky'''
        if param == 0:
            return uniform(0, 5)
        else:
            return 3.0

    The generated mutants look like this:

    0:
        def foo(param) -> float:
            if not param == 0:
                return uniform(0, 5)
            else:
                return 3.0
    1:
        def foo(param) -> float:
            if param == 1:
                return uniform(0, 5)
            else:
                return 3.0
    2:
        def foo(param) -> float:
            if param == 0:
                return uniform(1, 5)
            else:
                return 3.0
    3:
        def foo(param) -> float:
            if param == 0:
                return uniform(0, 6)
            else:
                return 3.0
    4:
        def foo(param) -> float:
            if param == 0:
                return uniform(0, 5)
            else:
                return 4.0
    5:
        def foo(param) -> float:
            if param != 0:
                return uniform(0, 5)
            else:
                return 3.0
    """

    config.configuration.module_name = "tests.fixtures.mutation.mutation"
    module_name = config.configuration.module_name
    tracer = ExecutionTracer()
    tracer.current_thread_identifier = threading.current_thread().ident
    with install_import_hook(module_name, tracer):
        importlib.reload(importlib.import_module(module_name))
        cluster = generate_test_cluster(module_name)
        transformer = AstToTestCaseTransformer(cluster, False, EmptyConstantProvider())
        transformer.visit(ast.parse(test_case_str))
        test_case = transformer.testcases[0]

        chromosome = tcc.TestCaseChromosome(test_case)
        suite = tsc.TestSuiteChromosome()
        suite.add_test_case_chromosome(chromosome)

        gen = ag.MutationAnalysisAssertionGenerator(TestCaseExecutor(tracer))
        with mock.patch.object(ag, "stat") as stat_mock:
            suite.accept(gen)
            stat_mock.assert_has_calls(
                [
                    call.track_output_variable(
                        RuntimeVariable.NumberOfKilledMutants, killed_mut
                    ),
                    call.track_output_variable(
                        RuntimeVariable.NumberOfTimedOutMutants, timeout_mut
                    ),
                    call.track_output_variable(
                        RuntimeVariable.NumberOfCreatedMutants, created_mut
                    ),
                    call.track_output_variable(
                        RuntimeVariable.MutationScore,
                        mut_score,  # pytest.approx does not work here
                    ),
                ]
            )

        visitor = tc_to_ast.TestCaseToAstVisitor(ns.NamingScope(prefix="module"), set())
        test_case.accept(visitor)
        source = ast.unparse(
            ast.fix_missing_locations(
                ast.Module(body=visitor.test_case_ast, type_ignores=[])
            )
        )
        assert source == test_case_str_with_assertions
