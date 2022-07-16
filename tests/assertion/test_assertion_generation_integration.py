#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
import ast
import importlib
import threading

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


@pytest.mark.parametrize(
    "generator,expected_result",
    [
        (
            ag.AssertionGenerator,
            """str_0 = 'foo bar'
float_0 = 39.82
human_0 = module_0.Human(str_0, float_0)
assert f'{type(human_0).__module__}.{type(human_0).__qualname__}' == 'tests.fixtures.examples.assertions.Human'
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


# Known mutants of tests.fixtures.mutation.mutation
_MUTANTS = [
    "from random import uniform\n"
    "\n"
    "def foo(param) -> float:\n"
    '    """This is flaky"""\n'
    "    if not param == 0:\n"
    "        return uniform(0, 5)\n"
    "    else:\n"
    "        return 3.0",
    "from random import uniform\n"
    "\n"
    "def foo(param) -> float:\n"
    '    """This is flaky"""\n'
    "    if param == 1:\n"
    "        return uniform(0, 5)\n"
    "    else:\n"
    "        return 3.0",
    "from random import uniform\n"
    "\n"
    "def foo(param) -> float:\n"
    '    """This is flaky"""\n'
    "    if param == 0:\n"
    "        return uniform(1, 5)\n"
    "    else:\n"
    "        return 3.0",
    "from random import uniform\n"
    "\n"
    "def foo(param) -> float:\n"
    '    """This is flaky"""\n'
    "    if param == 0:\n"
    "        return uniform(0, 6)\n"
    "    else:\n"
    "        return 3.0",
    "from random import uniform\n"
    "\n"
    "def foo(param) -> float:\n"
    '    """This is flaky"""\n'
    "    if param == 0:\n"
    "        return uniform(0, 5)\n"
    "    else:\n"
    "        return 4.0",
    "from random import uniform\n"
    "\n"
    "def foo(param) -> float:\n"
    '    """This is flaky"""\n'
    "    if param != 0:\n"
    "        return uniform(0, 5)\n"
    "    else:\n"
    "        return 3.0",
]


@pytest.mark.parametrize(
    "module,test_case_str,test_case_str_with_assertions,mutants,killed_mut,created_mut,timeout_mut,mut_score,killed,timeout",
    [
        (
            "tests.fixtures.mutation.mutation",
            """def test_case_0():
    int_0 = 1
    float_0 = module_0.foo(int_0)""",
            """int_0 = 1
float_0 = module_0.foo(int_0)
assert float_0 == pytest.approx(3.0, abs=0.01, rel=0.01)""",
            _MUTANTS,
            4,
            6,
            0,
            0.666,
            {0, 1, 4, 5},
            set(),
        ),
        (
            "tests.fixtures.mutation.mutation",
            """def test_case_0():
    int_0 = 0
    float_0 = module_0.foo(int_0)""",
            """int_0 = 0
float_0 = module_0.foo(int_0)""",
            _MUTANTS,
            0,
            6,
            0,
            0.0,
            set(),
            set(),
        ),
        (
            "tests.fixtures.mutation.exception",
            """def test_case_0():
    float_0 = module_0.foo(int_0)""",
            """module_0.foo()""",
            [
                "def foo() -> None:\n"
                "    alist = [2, 2]\n"
                "    assert len(alist) == 2\n"
                "    return None",
                "def foo() -> None:\n"
                "    alist = [1, 3]\n"
                "    assert len(alist) == 2\n"
                "    return None",
                "def foo() -> None:\n"
                "    alist = [1, 2]\n"
                "    assert len(alist) == 3\n"
                "    return None",
                "def foo() -> None:\n"
                "    alist = [1, 2]\n"
                "    assert len(alist) != 2\n"
                "    return None",
            ],
            2,
            4,
            0,
            0.5,
            {2, 3},
            set(),
        ),
    ],
)
def test_mutation_analysis_integration_full(
    module,
    test_case_str,
    test_case_str_with_assertions,
    mutants,
    killed_mut,
    created_mut,
    timeout_mut,
    mut_score,
    killed,
    timeout,
):
    config.configuration.module_name = module
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

        gen = ag.MutationAnalysisAssertionGenerator(
            TestCaseExecutor(tracer), testing=True
        )
        suite.accept(gen)

        mut_info = gen._testing_mutation_info
        assert {i for i, mut in enumerate(mut_info) if mut.killed_by} == killed
        assert {i for i, mut in enumerate(mut_info) if mut.timed_out_by} == timeout

        metrics = gen._compute_mutation_metrics(mut_info)
        assert metrics.num_timeout_mutants == timeout_mut
        assert metrics.num_killed_mutants == killed_mut
        assert metrics.num_created_mutants == created_mut
        assert metrics.get_score() == pytest.approx(mut_score, abs=1e-2)
        assert gen._testing_created_mutants == mutants
        visitor = tc_to_ast.TestCaseToAstVisitor(ns.NamingScope(prefix="module"), set())
        test_case.accept(visitor)
        source = ast.unparse(
            ast.fix_missing_locations(
                ast.Module(body=visitor.test_case_ast, type_ignores=[])
            )
        )
        assert source == test_case_str_with_assertions
