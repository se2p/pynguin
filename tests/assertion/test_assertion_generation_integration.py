#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
# ruff: noqa: E501
import ast
import importlib
import inspect
import threading

import pytest

import pynguin.assertion.assertiongenerator as ag
import pynguin.assertion.mutation_analysis.mutators as mu
import pynguin.assertion.mutation_analysis.operators as mo
import pynguin.configuration as config
import pynguin.ga.testcasechromosome as tcc
import pynguin.ga.testsuitechromosome as tsc
import pynguin.testcase.testcase_to_ast as tc_to_ast
import pynguin.utils.namingscope as ns

from pynguin.analyses.constants import EmptyConstantProvider
from pynguin.analyses.module import generate_test_cluster
from pynguin.analyses.seeding import AstToTestCaseTransformer
from pynguin.assertion.mutation_analysis.transformer import ParentNodeTransformer
from pynguin.instrumentation.machinery import install_import_hook
from pynguin.instrumentation.tracer import ExecutionTracer
from pynguin.testcase.execution import TestCaseExecutor


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
human_0.get_name()""",
        ),
    ],
)
def test_generate_mutation_assertions(generator, expected_result):  # noqa: PLR0914
    config.configuration.module_name = "tests.fixtures.examples.assertions"
    module_name = config.configuration.module_name
    tracer = ExecutionTracer()
    tracer.current_thread_identifier = threading.current_thread().ident
    with install_import_hook(module_name, tracer):
        module = importlib.import_module(module_name)
        importlib.reload(module)
        cluster = generate_test_cluster(module_name)
        transformer = AstToTestCaseTransformer(
            cluster,
            False,  # noqa: FBT003
            EmptyConstantProvider(),
        )
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

        if generator is ag.MutationAnalysisAssertionGenerator:
            mutant_generator = mu.FirstOrderMutator([
                *mo.standard_operators,
                *mo.experimental_operators,
            ])
            module_source_code = inspect.getsource(module)
            module_ast = ParentNodeTransformer.create_ast(module_source_code)
            mutation_tracer = ExecutionTracer()
            mutation_controller = ag.InstrumentedMutationController(
                mutant_generator, module_ast, module, mutation_tracer
            )
            gen = generator(TestCaseExecutor(tracer), mutation_controller)
        else:
            gen = generator(TestCaseExecutor(tracer))
        suite.accept(gen)

        visitor = tc_to_ast.TestCaseToAstVisitor(ns.NamingScope(prefix="module"), set())
        test_case.accept(visitor)
        source = ast.unparse(
            ast.fix_missing_locations(ast.Module(body=visitor.test_case_ast, type_ignores=[]))
        )
        assert source == expected_result


# Known mutants of tests.fixtures.mutation.mutation
_MUTANTS = [
    "from time import sleep\nfrom time import time_ns\n"
    "\n"
    "def foo(param) -> float:\n"
    '    """This is flaky"""\n'
    "    if not param == 0:\n"
    "        sleep(0.1)\n"
    "        return time_ns()\n"
    "    else:\n"
    "        return 2.0",
    "from time import sleep\nfrom time import time_ns\n"
    "\n"
    "def foo(param) -> float:\n"
    '    """This is flaky"""\n'
    "    if param == 1:\n"
    "        sleep(0.1)\n"
    "        return time_ns()\n"
    "    else:\n"
    "        return 2.0",
    "from time import sleep\nfrom time import time_ns\n"
    "\n"
    "def foo(param) -> float:\n"
    '    """This is flaky"""\n'
    "    if param == 0:\n"
    "        sleep(1.1)\n"
    "        return time_ns()\n"
    "    else:\n"
    "        return 2.0",
    "from time import sleep\nfrom time import time_ns\n"
    "\n"
    "def foo(param) -> float:\n"
    '    """This is flaky"""\n'
    "    if param == 0:\n"
    "        sleep(0.1)\n"
    "        return time_ns()\n"
    "    else:\n"
    "        return 3.0",
    "from time import sleep\nfrom time import time_ns\n"
    "\n"
    "def foo(param) -> float:\n"
    '    """This is flaky"""\n'
    "    if param != 0:\n"
    "        sleep(0.1)\n"
    "        return time_ns()\n"
    "    else:\n"
    "        return 2.0",
]


@pytest.mark.filterwarnings("ignore::pytest.PytestUnhandledThreadExceptionWarning")
@pytest.mark.parametrize(
    "module,test_case_str,test_case_str_with_assertions,mutants,metrics,killed,timeout",
    [
        (
            "tests.fixtures.mutation.mutation",
            "def test_case_0():\n    int_0 = 0\n    int_1 = 0\n    int_2 = 0\n"
            "    int_3 = 1\n    float_0 = module_0.foo(int_3)",
            "int_0 = 0\nint_1 = 0\nint_2 = 0\nint_3 = 1\nfloat_0 = "
            "module_0.foo(int_3)\n"
            "assert float_0 == pytest.approx(2.0, abs=0.01, rel=0.01)",
            _MUTANTS,
            ag._MutationMetrics(5, 4, 0),
            {0, 1, 3, 4},
            set(),
        ),
        (
            "tests.fixtures.mutation.mutation",
            "def test_case_0():\n    int_0 = 0\n    int_1 = 0\n    int_2 = 0\n"
            "    int_3 = 0\n    float_0 = module_0.foo(int_3)",
            "int_0 = 0\nint_1 = 0\nint_2 = 0\nint_3 = 0\nmodule_0.foo(int_3)",
            _MUTANTS,
            ag._MutationMetrics(5, 0, 0),
            set(),
            set(),
        ),
        (
            "tests.fixtures.mutation.exception",
            "def test_case_0():\n    float_0 = module_0.foo()",
            "module_0.foo()",
            [
                "def foo() -> None:\n"
                "    alist = [1, 2]\n"
                "    if not len(alist) != 2:\n"
                "        raise ValueError()\n"
                "    return None",
                "def foo() -> None:\n"
                "    alist = [2, 2]\n"
                "    if len(alist) != 2:\n"
                "        raise ValueError()\n"
                "    return None",
                "def foo() -> None:\n"
                "    alist = [1, 3]\n"
                "    if len(alist) != 2:\n"
                "        raise ValueError()\n"
                "    return None",
                "def foo() -> None:\n"
                "    alist = [1, 2]\n"
                "    if len(alist) != 3:\n"
                "        raise ValueError()\n"
                "    return None",
                "def foo() -> None:\n"
                "    alist = [1, 2]\n"
                "    if len(alist) == 2:\n"
                "        raise ValueError()\n"
                "    return None",
            ],
            ag._MutationMetrics(5, 3, 0),
            {0, 3, 4},
            set(),
        ),
        (
            "tests.fixtures.mutation.expected",
            "def test_case_0():\n    int_0 = 2\n    var_0 = module_0.bar(int_0)",
            "int_0 = 2\nwith pytest.raises(ValueError):\n    var_0 = module_0.bar(int_0)",
            [
                "def bar(foo):\n    if not foo == 2:\n        raise ValueError()",
                "def bar(foo):\n    if foo == 3:\n        raise ValueError()",
                "def bar(foo):\n    if foo != 2:\n        raise ValueError()",
            ],
            ag._MutationMetrics(3, 3, 0),
            {0, 1, 2},
            set(),
        ),
        (
            "tests.fixtures.mutation.timeout",
            "def test_case_0():\n    int_0 = 1\n    var_0 = module_0.timeout(int_0)",
            "int_0 = 1\nvar_0 = module_0.timeout(int_0)\nassert var_0 == 5",
            [
                "import time\n"
                "\n"
                "def timeout(foo):\n"
                "    if not foo == 2:\n"
                "        time.sleep(4)\n"
                "    return 5",
                "import time\n"
                "\n"
                "def timeout(foo):\n"
                "    if foo == 3:\n"
                "        time.sleep(4)\n"
                "    return 5",
                "import time\n"
                "\n"
                "def timeout(foo):\n"
                "    if foo == 2:\n"
                "        time.sleep(5)\n"
                "    return 5",
                "import time\n"
                "\n"
                "def timeout(foo):\n"
                "    if foo == 2:\n"
                "        time.sleep(4)\n"
                "    return 6",
                "import time\n"
                "\n"
                "def timeout(foo):\n"
                "    if foo != 2:\n"
                "        time.sleep(4)\n"
                "    return 5",
            ],
            ag._MutationMetrics(5, 1, 2),
            {3},
            {0, 4},
        ),
    ],
)
def test_mutation_analysis_integration_full(  # noqa: PLR0914, PLR0917
    module,
    test_case_str,
    test_case_str_with_assertions,
    mutants,
    metrics,
    killed,
    timeout,
):
    config.configuration.module_name = module
    module_name = config.configuration.module_name
    tracer = ExecutionTracer()
    tracer.current_thread_identifier = threading.current_thread().ident
    with install_import_hook(module_name, tracer):
        module_type = importlib.import_module(module_name)
        importlib.reload(module_type)
        cluster = generate_test_cluster(module_name)
        transformer = AstToTestCaseTransformer(
            cluster,
            False,  # noqa: FBT003
            EmptyConstantProvider(),
        )
        transformer.visit(ast.parse(test_case_str))
        test_case = transformer.testcases[0]

        chromosome = tcc.TestCaseChromosome(test_case)
        suite = tsc.TestSuiteChromosome()
        suite.add_test_case_chromosome(chromosome)

        mutant_generator = mu.FirstOrderMutator([
            *mo.standard_operators,
            *mo.experimental_operators,
        ])
        module_source_code = inspect.getsource(module_type)
        module_ast = ParentNodeTransformer.create_ast(module_source_code)
        mutation_tracer = ExecutionTracer()
        mutation_controller = ag.InstrumentedMutationController(
            mutant_generator, module_ast, module_type, mutation_tracer, testing=True
        )
        gen = ag.MutationAnalysisAssertionGenerator(
            TestCaseExecutor(tracer), mutation_controller, testing=True
        )
        suite.accept(gen)

        summary = gen._testing_mutation_summary
        kills = {k.mut_num for k in summary.get_killed()}
        timeouts = {k.mut_num for k in summary.get_timeout()}
        survived = {k.mut_num for k in summary.get_survived()}
        assert kills == killed
        assert timeouts == timeout
        # Test for disjoint
        assert len(kills | survived | timeouts) == len(kills) + len(timeouts) + len(survived)

        assert summary.get_metrics() == metrics
        assert mutation_controller._testing_created_mutants == mutants
        visitor = tc_to_ast.TestCaseToAstVisitor(ns.NamingScope(prefix="module"), set())
        test_case.accept(visitor)
        source = ast.unparse(
            ast.fix_missing_locations(ast.Module(body=visitor.test_case_ast, type_ignores=[]))
        )
        assert source == test_case_str_with_assertions
        for thread in threading.enumerate():
            if "_execute_test_case" in thread.name:
                thread.join()
        assert len(threading.enumerate()) == 1  # Only main thread should be alive.
