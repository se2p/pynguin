#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
# ruff: noqa: E501
import ast
import importlib
import inspect
import tempfile
import threading
from pathlib import Path

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
from pynguin.assertion.mutation_analysis.controller import MutationController
from pynguin.assertion.mutation_analysis.transformer import ParentNodeTransformer
from pynguin.instrumentation.machinery import install_import_hook
from pynguin.instrumentation.tracer import SubjectProperties
from pynguin.testcase import export
from pynguin.testcase.execution import TestCaseExecutor
from tests.testutils import extract_test_case_0


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
def test_generate_mutation_assertions(
    generator, expected_result, subject_properties: SubjectProperties
):
    config.configuration.module_name = "tests.fixtures.examples.assertions"
    module_name = config.configuration.module_name
    with install_import_hook(module_name, subject_properties):
        with subject_properties.instrumentation_tracer:
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
            mutation_controller = MutationController(mutant_generator, module_ast, module)
            gen = generator(TestCaseExecutor(subject_properties), mutation_controller)
        else:
            gen = generator(TestCaseExecutor(subject_properties))
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
            "int_0 = 2\nwith pytest.raises(ValueError):\n    module_0.bar(int_0)",
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
    subject_properties: SubjectProperties,
):
    config.configuration.module_name = module
    module_name = config.configuration.module_name
    with install_import_hook(module_name, subject_properties):
        with subject_properties.instrumentation_tracer:
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
        mutation_controller = MutationController(mutant_generator, module_ast, module_type)
        gen = ag.MutationAnalysisAssertionGenerator(
            TestCaseExecutor(subject_properties), mutation_controller, testing=True
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
        assert [
            ast.unparse(mutant_ast)
            for _, mutant_ast in mutant_generator.mutate(module_ast, module_type)
        ] == mutants
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


def _add_assertions(module_name: str, test_case_code: str) -> str:
    """Add assertions to a test case and return the test case with assertions.

    Existing assertions in the given test case are ignored.

    Args:
        module_name: The name of the SUT module.
        test_case_code: The test case code to add assertions for.

    Returns:
        A test case with assertions.
    """
    subject_properties = SubjectProperties()
    config.configuration.module_name = module_name
    test_case_code = "import " + module_name + " as module_0\n\n" + test_case_code

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)

        # Parse seed into DefaultTestCase
        test_cluster = generate_test_cluster(module_name)
        transformer = AstToTestCaseTransformer(
            test_cluster=test_cluster,
            create_assertions=False,  # do not import existing assertions; we'll generate them
            constant_provider=EmptyConstantProvider(),
        )
        transformer.visit(ast.parse(test_case_code))
        assert transformer.testcases, "No test case parsed from seed source"
        test_case_chrom = tcc.TestCaseChromosome(transformer.testcases[0])

        # Instrument and import target module for assertion generation
        with install_import_hook(module_name, subject_properties):
            with subject_properties.instrumentation_tracer:
                module = importlib.import_module(module_name)
                importlib.reload(module)

            # Execute the imported test case
            executor = TestCaseExecutor(subject_properties)
            execution_result = executor.execute(test_case_chrom.test_case)
            test_case_chrom.set_last_execution_result(execution_result)

            # Generate assertions
            executor = TestCaseExecutor(subject_properties)
            ag.AssertionGenerator(executor).visit_test_case_chromosome(test_case_chrom)

            # Export the augmented test with assertions
            export_path = tmp_path / "test_with_assertions.py"
            exporter = export.PyTestChromosomeToAstVisitor(store_call_return=False)
            test_case_chrom.accept(exporter)
            export.save_module_to_file(
                exporter.to_module(),
                export_path,
                format_with_black=config.configuration.test_case_output.format_with_black,
            )

        exported = export_path.read_text(encoding="utf-8")
        return extract_test_case_0(exported)


@pytest.mark.parametrize(
    "module_name,test_case_code,expected_code",
    [
        # Simple case
        (
            "tests.fixtures.accessibles.accessible",
            """def test_case_0():
    int_0 = 5
    some_type_0 = module_0.SomeType(int_0)
    assert (
        f"{type(some_type_0).__module__}.{type(some_type_0).__qualname__}"
        == "tests.fixtures.accessibles.accessible.SomeType"
    )
    float_0 = 42.23
    float_1 = module_0.simple_function(float_0)
    assert float_1 == pytest.approx(42.23, abs=0.01, rel=0.01)""",
            None,
        ),
        # No exceptions
        (
            "tests.fixtures.examples.unasserted_exceptions",
            """def test_case_0():
    bool_0 = True
    bool_1 = module_0.foo(bool_0)
    assert bool_1 is False""",
            None,
        ),
        # Unexpected exception
        (
            "tests.fixtures.examples.unasserted_exceptions",
            """def test_case_0():
    int_0 = 24
    bool_0 = module_0.foo(int_0)""",
            """@pytest.mark.xfail(strict=True)
def test_case_0():
    int_0 = 24
    module_0.foo(int_0)""",
        ),
        # Expected exception
        (
            "tests.fixtures.examples.unasserted_exceptions",
            """def test_case_0():
    none_type_0 = None
    bool_0 = module_0.foo(none_type_0)
    assert bool_0 is False""",
            """def test_case_0():
    none_type_0 = None
    with pytest.raises(AssertionError):
        module_0.foo(none_type_0)""",
        ),
    ],
)
def test_add_assertions(module_name: str, test_case_code: str, expected_code: str | None):
    with_assertions_code = _add_assertions(module_name, test_case_code)
    if expected_code is None:
        assert with_assertions_code == test_case_code
    else:
        assert with_assertions_code == expected_code
