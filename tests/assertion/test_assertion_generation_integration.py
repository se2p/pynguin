#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Integration tests for mutation-analysis-driven assertion generation.

These tests drive the *real* assertion-generation subsystem end to end: they
build libcst-backed test cases with the current ``tests/testcase/_builders``
helpers, execute them against instrumented fixture modules, and let
:class:`AssertionGenerator` / :class:`MutationAnalysisAssertionGenerator` add,
filter and mutation-minimize assertions. The resulting test case is rendered
back to source with the current :class:`TestSuiteWriter` and compared against
the expected pytest code.

Test cases are constructed directly from statements and the SUT is referenced
through the module alias returned by :func:`get_module_alias` (e.g. ``mutation_``).
"""

import ast
import builtins
import importlib
import inspect
import threading
from unittest import mock

import libcst as cst
import pytest

import pynguin.assertion.assertion as ass
import pynguin.assertion.assertiongenerator as ag
import pynguin.assertion.mutation_analysis.mutators as mu
import pynguin.assertion.mutation_analysis.operators as mo
import pynguin.configuration as config
import pynguin.ga.testcasechromosome as tcc
import pynguin.ga.testsuitechromosome as tsc
import pynguin.testcase.testcase as tc
from pynguin.assertion.mutation_analysis.controller import MutationController
from pynguin.assertion.mutation_analysis.transformer import ParentNodeTransformer
from pynguin.instrumentation.machinery import install_import_hook
from pynguin.instrumentation.tracer import SubjectProperties
from pynguin.testcase.execution import TestCaseExecutor
from pynguin.testcase.export import TestSuiteWriter
from pynguin.utils.generic.genericaccessibleobject import GenericCallableAccessibleObject
from pynguin.utils.naming import get_module_alias
from tests.testcase._builders import (
    assign,
    bool_stmt,
    call_stmt,
    float_stmt,
    int_stmt,
    make_test_case,
    str_stmt,
)


class OriginalConstantReplacement(mo.ConstantReplacement):
    def mutate_Constant_num_zero(self, node):  # noqa: N802
        return None

    def mutate_Constant_num_neg(self, node):  # noqa: N802
        return None

    def mutate_Constant_num_decrement(self, node):  # noqa: N802
        return None


test_operators: list[type[mo.MutationOperator]] = [
    mo.ArithmeticOperatorDeletion,
    mo.ArithmeticOperatorReplacement,
    mo.AssignmentOperatorReplacement,
    mo.BreakContinueReplacement,
    mo.ConditionalOperatorDeletion,
    mo.ConditionalOperatorInsertion,
    OriginalConstantReplacement,
    mo.DecoratorDeletion,
    mo.ExceptionHandlerDeletion,
    mo.ExceptionSwallowing,
    mo.HidingVariableDeletion,
    mo.LogicalConnectorReplacement,
    mo.LogicalOperatorDeletion,
    mo.LogicalOperatorReplacement,
    mo.OverriddenMethodCallingPositionChange,
    mo.OverridingMethodDeletion,
    mo.RelationalOperatorReplacement,
    mo.SliceIndexRemove,
    mo.SuperCallingDeletion,
    mo.SuperCallingInsert,
]


# -- HELPERS ---------------------------------------------------------------------------


def _standard_mutant_generator() -> mu.FirstOrderMutator:
    """The mutant generator used by the integration fixtures."""
    return mu.FirstOrderMutator([
        *test_operators,
        mo.OneIterationLoop,
        mo.ReverseIterationLoop,
        mo.ZeroIterationLoop,
    ])


def _mutation_controller(mutant_generator, module, module_ast) -> MutationController:
    return MutationController(mutant_generator, module_ast, module)


def _module_ast(module) -> ast.Module:
    return ParentNodeTransformer.create_ast(inspect.getsource(module))


def _suite(test_case: tc.TestCase) -> tsc.TestSuiteChromosome:
    suite = tsc.TestSuiteChromosome()
    suite.add_test_case_chromosome(tcc.TestCaseChromosome(test_case))
    return suite


def _resolve_exception_type(name: str) -> type[BaseException]:
    resolved = getattr(builtins, name, None)
    if isinstance(resolved, type) and issubclass(resolved, BaseException):
        return resolved
    return type(name, (BaseException,), {})


def _render(test_case: tc.TestCase) -> str:
    """Render a single test case to pytest source with the current writer.

    A statement that carries an :class:`ExceptionAssertion` (produced by the
    generator when re-execution raised) is wrapped in ``pytest.raises(...)``,
    matching what the exporter emits for an expected exception. The exception
    type and the ``pytest.raises`` wrapping are both derived from the generated
    assertion, so the rendering reflects the real generation outcome.
    """
    writer = TestSuiteWriter()
    exc_types: list[type[BaseException] | None] = []
    for statement in test_case.statements():
        exception_assertion = next(
            (a for a in statement.assertions if isinstance(a, ass.ExceptionAssertion)),
            None,
        )
        if exception_assertion is None:
            exc_types.append(None)
            continue
        exc_type = _resolve_exception_type(exception_assertion.exception_type_name)
        accessible = mock.Mock(spec=GenericCallableAccessibleObject)
        accessible.expected_exceptions = {exc_type.__name__}
        statement.accessible = accessible
        exc_types.append(exc_type)
    func, _ = writer._build_test_function(0, test_case, exc_types)
    return cst.Module(body=[func]).code


def _exception_assertion_names(test_case: tc.TestCase) -> list[str]:
    """Return the exception-type names recorded by ExceptionAssertions, in order."""
    return [
        assertion.exception_type_name
        for statement in test_case.statements()
        for assertion in statement.assertions
        if isinstance(assertion, ass.ExceptionAssertion)
    ]


# -- TEST-CASE FACTORIES ---------------------------------------------------------------
# Each builds the libcst test case for a fixture module, referencing the SUT through
# its module alias (e.g. ``mutation_``) exactly as the current pipeline does.


def _tc_assertions(alias: str) -> tc.TestCase:
    return make_test_case(
        str_stmt("str_0", "foo bar"),
        float_stmt("float_0", 39.82),
        call_stmt("human_0", f"{alias}.Human(str_0, float_0)"),
        call_stmt("str_1", "human_0.get_name()", bound_type=str),
    )


def _tc_mutation_killing(alias: str) -> tc.TestCase:
    return make_test_case(
        int_stmt("int_3", 1),
        call_stmt("float_0", f"{alias}.foo(int_3)", bound_type=float),
    )


def _tc_mutation_non_killing(alias: str) -> tc.TestCase:
    return make_test_case(
        int_stmt("int_3", 0),
        call_stmt("float_0", f"{alias}.foo(int_3)", bound_type=float),
    )


def _tc_exception(alias: str) -> tc.TestCase:
    return make_test_case(
        call_stmt("float_0", f"{alias}.foo()", bound_type=float),
    )


def _tc_expected(alias: str) -> tc.TestCase:
    return make_test_case(
        int_stmt("int_0", 2),
        call_stmt("var_0", f"{alias}.bar(int_0)"),
    )


def _tc_timeout(alias: str) -> tc.TestCase:
    return make_test_case(
        int_stmt("int_0", 1),
        call_stmt("var_0", f"{alias}.timeout(int_0)", bound_type=int),
    )


# Rendered sources (current TestSuiteWriter output; the SUT alias is fixture-specific).
_ASSERTIONS_REGRESSION_SOURCE = (
    "def test_0():\n"
    "    str_0 = 'foo bar'\n"
    "    assert str_0 == 'foo bar'\n"
    "    assert assertions_.static_state == 0\n"
    "    float_0 = 39.82\n"
    "    assert float_0 == pytest.approx(39.82, abs=0.01, rel=0.01)\n"
    "    human_0 = assertions_.Human(str_0, float_0)\n"
    "    assert isinstance(human_0, assertions_.Human)\n"
    "    str_1 = human_0.get_name()\n"
    "    assert str_1 == 'foo bar'\n"
)

_ASSERTIONS_MUTATION_SOURCE = (
    "def test_0():\n"
    "    str_0 = 'foo bar'\n"
    "    assert assertions_.static_state == 0\n"
    "    float_0 = 39.82\n"
    "    human_0 = assertions_.Human(str_0, float_0)\n"
    "    str_1 = human_0.get_name()\n"
)


@pytest.mark.parametrize(
    "generator,expected_source",
    [
        (ag.AssertionGenerator, _ASSERTIONS_REGRESSION_SOURCE),
        (ag.MutationAnalysisAssertionGenerator, _ASSERTIONS_MUTATION_SOURCE),
    ],
)
def test_generate_mutation_assertions(
    generator, expected_source, subject_properties: SubjectProperties
):
    """Regression assertions vs. mutation-filtered assertions on the same test case.

    The plain :class:`AssertionGenerator` keeps every regression assertion; the
    :class:`MutationAnalysisAssertionGenerator` keeps only the single assertion
    (``static_state == 0``) that actually kills a mutant.
    """
    module_name = "tests.fixtures.examples.assertions"
    config.configuration.module_name = module_name
    alias = get_module_alias(module_name)
    with install_import_hook(module_name, subject_properties):
        with subject_properties.instrumentation_tracer:
            module = importlib.import_module(module_name)
            importlib.reload(module)

        test_case = _tc_assertions(alias)
        suite = _suite(test_case)

        if generator is ag.MutationAnalysisAssertionGenerator:
            module_ast = _module_ast(module)
            controller = _mutation_controller(_standard_mutant_generator(), module, module_ast)
            gen = generator(TestCaseExecutor(subject_properties), controller)
        else:
            gen = generator(TestCaseExecutor(subject_properties))
        suite.accept(gen)

        assert _render(test_case) == expected_source


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

_EXCEPTION_MUTANTS = [
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
]

_EXPECTED_MUTANTS = [
    "def bar(foo):\n    if not foo == 2:\n        raise ValueError()",
    "def bar(foo):\n    if foo == 3:\n        raise ValueError()",
    "def bar(foo):\n    if foo != 2:\n        raise ValueError()",
]

_TIMEOUT_MUTANTS = [
    "import time\n\ndef timeout(foo):\n    if not foo == 2:\n        time.sleep(4)\n    return 5",
    "import time\n\ndef timeout(foo):\n    if foo == 3:\n        time.sleep(4)\n    return 5",
    "import time\n\ndef timeout(foo):\n    if foo == 2:\n        time.sleep(5)\n    return 5",
    "import time\n\ndef timeout(foo):\n    if foo == 2:\n        time.sleep(4)\n    return 6",
    "import time\n\ndef timeout(foo):\n    if foo != 2:\n        time.sleep(4)\n    return 5",
]


@pytest.mark.filterwarnings("ignore::pytest.PytestUnhandledThreadExceptionWarning")
@pytest.mark.parametrize(
    "module,tc_factory,expected_source,mutants,metrics,killed,timeout",
    [
        (
            "tests.fixtures.mutation.mutation",
            _tc_mutation_killing,
            "def test_0():\n"
            "    int_3 = 1\n"
            "    float_0 = mutation_.foo(int_3)\n"
            "    assert float_0 == pytest.approx(2.0, abs=0.01, rel=0.01)\n",
            _MUTANTS,
            ag._MutationMetrics(5, 4, 0),
            {0, 1, 3, 4},
            set(),
        ),
        (
            "tests.fixtures.mutation.mutation",
            _tc_mutation_non_killing,
            "def test_0():\n    int_3 = 0\n    float_0 = mutation_.foo(int_3)\n",
            _MUTANTS,
            ag._MutationMetrics(5, 0, 0),
            set(),
            set(),
        ),
        (
            "tests.fixtures.mutation.exception",
            _tc_exception,
            "def test_0():\n    float_0 = exception_.foo()\n",
            _EXCEPTION_MUTANTS,
            ag._MutationMetrics(5, 3, 0),
            {0, 3, 4},
            set(),
        ),
        (
            "tests.fixtures.mutation.expected",
            _tc_expected,
            "def test_0():\n"
            "    int_0 = 2\n"
            "    with pytest.raises(ValueError):\n"
            "        var_0 = expected_.bar(int_0)\n",
            _EXPECTED_MUTANTS,
            ag._MutationMetrics(3, 3, 0),
            {0, 1, 2},
            set(),
        ),
        (
            "tests.fixtures.mutation.timeout",
            _tc_timeout,
            "def test_0():\n"
            "    int_0 = 1\n"
            "    var_0 = timeout_.timeout(int_0)\n"
            "    assert var_0 == 5\n",
            _TIMEOUT_MUTANTS,
            ag._MutationMetrics(5, 1, 2),
            {3},
            {0, 4},
        ),
    ],
)
def test_mutation_analysis_integration_full(  # noqa: PLR0917
    module,
    tc_factory,
    expected_source,
    mutants,
    metrics,
    killed,
    timeout,
    subject_properties: SubjectProperties,
):
    config.configuration.module_name = module
    alias = get_module_alias(module)
    with install_import_hook(module, subject_properties):
        with subject_properties.instrumentation_tracer:
            module_type = importlib.import_module(module)
            importlib.reload(module_type)

        test_case = tc_factory(alias)
        suite = _suite(test_case)

        mutant_generator = _standard_mutant_generator()
        module_ast = _module_ast(module_type)
        controller = _mutation_controller(mutant_generator, module_type, module_ast)
        gen = ag.MutationAnalysisAssertionGenerator(
            TestCaseExecutor(subject_properties), controller, testing=True
        )
        suite.accept(gen)

        summary = gen._testing_mutation_summary
        kills = {k.mut_num for k in summary.get_killed()}
        timeouts = {k.mut_num for k in summary.get_timeout()}
        survived = {k.mut_num for k in summary.get_survived()}
        assert kills == killed
        assert timeouts == timeout
        # Killed, survived and timed-out sets are disjoint.
        assert len(kills | survived | timeouts) == len(kills) + len(timeouts) + len(survived)

        assert summary.get_metrics() == metrics
        assert [
            ast.unparse(mutant_ast)
            for _, mutant_ast in mutant_generator.mutate(module_ast, module_type)
        ] == mutants

        assert _render(test_case) == expected_source

        for thread in threading.enumerate():
            if "_execute_test_case" in thread.name:
                thread.join()
        assert len(threading.enumerate()) == 1  # Only main thread should be alive.


@pytest.mark.filterwarnings("ignore::pytest.PytestUnhandledThreadExceptionWarning")
def test_mutation_analysis_truncated_by_mutant_cap(
    subject_properties: SubjectProperties,
):
    module = "tests.fixtures.mutation.mutation"
    config.configuration.module_name = module
    config.configuration.seeding.seed = 42
    alias = get_module_alias(module)
    with install_import_hook(module, subject_properties):
        with subject_properties.instrumentation_tracer:
            module_type = importlib.import_module(module)
            importlib.reload(module_type)

        test_case = _tc_mutation_killing(alias)
        suite = _suite(test_case)

        cap = 2
        mutant_generator = mu.FirstOrderMutator(
            [*mo.standard_operators, *mo.experimental_operators],
            maximum_mutants=cap,
            sampling_seed=config.configuration.seeding.seed,
            reorder=True,
        )
        module_ast = _module_ast(module_type)
        controller = _mutation_controller(mutant_generator, module_type, module_ast)

        # The module yields more mutants than the cap.
        num_created = controller.mutant_count()
        assert num_created > cap

        gen = ag.MutationAnalysisAssertionGenerator(
            TestCaseExecutor(subject_properties), controller, testing=True
        )
        suite.accept(gen)

        summary = gen._testing_mutation_summary
        num_checked = len(summary.mutant_information)

        # Only the sampled mutants are checked, and they form the score denominator.
        assert num_checked == cap
        assert num_checked < num_created

        for thread in threading.enumerate():
            if "_execute_test_case" in thread.name:
                thread.join()
        assert len(threading.enumerate()) == 1


@pytest.mark.filterwarnings("ignore::pytest.PytestUnhandledThreadExceptionWarning")
def test_mutation_analysis_truncated_by_time_budget(subject_properties: SubjectProperties):
    module = "tests.fixtures.mutation.mutation"
    config.configuration.module_name = module
    config.configuration.seeding.seed = 42
    original_budget = config.configuration.test_case_output.maximum_mutation_time
    # A zero-second budget stops before the first mutant is checked.
    config.configuration.test_case_output.maximum_mutation_time = 0
    alias = get_module_alias(module)
    try:
        with install_import_hook(module, subject_properties):
            with subject_properties.instrumentation_tracer:
                module_type = importlib.import_module(module)
                importlib.reload(module_type)

            test_case = _tc_mutation_killing(alias)
            suite = _suite(test_case)

            mutant_generator = mu.FirstOrderMutator([
                *mo.standard_operators,
                *mo.experimental_operators,
            ])
            module_ast = _module_ast(module_type)
            controller = _mutation_controller(mutant_generator, module_type, module_ast)

            num_created = controller.mutant_count()
            assert num_created > 0

            gen = ag.MutationAnalysisAssertionGenerator(
                TestCaseExecutor(subject_properties), controller, testing=True
            )
            suite.accept(gen)

            # The budget cut every mutant; the run still completes cleanly.
            assert len(gen._testing_mutation_summary.mutant_information) == 0

            for thread in threading.enumerate():
                if "_execute_test_case" in thread.name:
                    thread.join()
            assert len(threading.enumerate()) == 1
    finally:
        config.configuration.test_case_output.maximum_mutation_time = original_budget


@pytest.mark.parametrize(
    "module,tc_factory,expected_source,killed,timeout",
    [
        # Value assertion that kills mutants is kept.
        (
            "tests.fixtures.mutation.mutation",
            _tc_mutation_killing,
            "def test_0():\n"
            "    int_3 = 1\n"
            "    float_0 = mutation_.foo(int_3)\n"
            "    assert float_0 == pytest.approx(2.0, abs=0.01, rel=0.01)\n",
            {0, 1, 3, 4},
            set(),
        ),
        # Assertion that kills nothing is dropped (subsumes kills-nothing removal).
        (
            "tests.fixtures.mutation.mutation",
            _tc_mutation_non_killing,
            "def test_0():\n    int_3 = 0\n    float_0 = mutation_.foo(int_3)\n",
            set(),
            set(),
        ),
        # Statement with only an exception assertion is left untouched.
        (
            "tests.fixtures.mutation.exception",
            _tc_exception,
            "def test_0():\n    float_0 = exception_.foo()\n",
            {0, 3, 4},
            set(),
        ),
        # Expected-exception (pytest.raises) case is preserved.
        (
            "tests.fixtures.mutation.expected",
            _tc_expected,
            "def test_0():\n"
            "    int_0 = 2\n"
            "    with pytest.raises(ValueError):\n"
            "        var_0 = expected_.bar(int_0)\n",
            {0, 1, 2},
            set(),
        ),
    ],
)
def test_mutation_analysis_minimization_preserves_output(  # noqa: PLR0917
    module,
    tc_factory,
    expected_source,
    killed,
    timeout,
    subject_properties: SubjectProperties,
):
    """With minimization on, already-minimal outputs are reproduced exactly.

    These fixtures produce assertions that are either uniquely required or kill
    nothing, so greedy set cover must keep exactly the same assertions as the
    default path while preserving the killed mutants.
    """
    original_minimization = config.configuration.test_case_output.assertion_minimization
    config.configuration.test_case_output.assertion_minimization = True
    try:
        config.configuration.module_name = module
        alias = get_module_alias(module)
        with install_import_hook(module, subject_properties):
            with subject_properties.instrumentation_tracer:
                module_type = importlib.import_module(module)
                importlib.reload(module_type)

            test_case = tc_factory(alias)
            suite = _suite(test_case)

            mutant_generator = _standard_mutant_generator()
            module_ast = _module_ast(module_type)
            controller = _mutation_controller(mutant_generator, module_type, module_ast)
            gen = ag.MutationAnalysisAssertionGenerator(
                TestCaseExecutor(subject_properties), controller, testing=True
            )
            suite.accept(gen)

            summary = gen._testing_mutation_summary
            assert {k.mut_num for k in summary.get_killed()} == killed
            assert {k.mut_num for k in summary.get_timeout()} == timeout

            assert _render(test_case) == expected_source

            for thread in threading.enumerate():
                if "_execute_test_case" in thread.name:
                    thread.join()
    finally:
        config.configuration.test_case_output.assertion_minimization = original_minimization


@pytest.mark.parametrize(
    "module_name,tc_factory,expected_source",
    [
        # Regression assertions on primitives, an isinstance check and a float result.
        (
            "tests.fixtures.accessibles.accessible",
            lambda alias: make_test_case(
                int_stmt("int_0", 5),
                call_stmt("some_type_0", f"{alias}.SomeType(int_0)"),
                float_stmt("float_0", 42.23),
                call_stmt("float_1", f"{alias}.simple_function(float_0)", bound_type=float),
            ),
            "def test_0():\n"
            "    int_0 = 5\n"
            "    assert int_0 == 5\n"
            "    some_type_0 = accessible_.SomeType(int_0)\n"
            "    assert isinstance(some_type_0, accessible_.SomeType)\n"
            "    float_0 = 42.23\n"
            "    assert float_0 == pytest.approx(42.23, abs=0.01, rel=0.01)\n"
            "    float_1 = accessible_.simple_function(float_0)\n"
            "    assert float_1 == pytest.approx(42.23, abs=0.01, rel=0.01)\n",
        ),
        # A non-raising boolean call gets a regression value assertion.
        (
            "tests.fixtures.examples.unasserted_exceptions",
            lambda alias: make_test_case(
                bool_stmt("bool_0", True),  # noqa: FBT003
                call_stmt("bool_1", f"{alias}.foo(bool_0)", bound_type=bool),
            ),
            "def test_0():\n"
            "    bool_0 = True\n"
            "    assert bool_0 is True\n"
            "    bool_1 = unasserted_exceptions_.foo(bool_0)\n"
            "    assert bool_1 is False\n",
        ),
    ],
)
def test_add_regression_assertions(
    module_name: str, tc_factory, expected_source: str, subject_properties: SubjectProperties
):
    """The plain assertion generator adds regression assertions to a seed test case."""
    config.configuration.module_name = module_name
    alias = get_module_alias(module_name)
    with install_import_hook(module_name, subject_properties):
        with subject_properties.instrumentation_tracer:
            module = importlib.import_module(module_name)
            importlib.reload(module)

        test_case = tc_factory(alias)
        suite = _suite(test_case)
        suite.accept(ag.AssertionGenerator(TestCaseExecutor(subject_properties)))

        assert _render(test_case) == expected_source


@pytest.mark.parametrize(
    "tc_factory,expected_exception_name",
    [
        # A call that raises records the raised exception type as an assertion.
        (
            lambda alias: make_test_case(
                int_stmt("int_0", 24),
                call_stmt("bool_0", f"{alias}.foo(int_0)", bound_type=bool),
            ),
            "ZeroDivisionError",
        ),
        (
            lambda alias: make_test_case(
                assign("none_type_0", "None"),
                call_stmt("bool_0", f"{alias}.foo(none_type_0)", bound_type=bool),
            ),
            "AssertionError",
        ),
    ],
)
def test_add_exception_assertion(
    tc_factory, expected_exception_name: str, subject_properties: SubjectProperties
):
    """Assertion generation records the exception raised while executing a statement.

    The old pipeline distinguished *expected* from *unexpected* exceptions at
    export time using cluster-attached accessibles (``pytest.raises`` vs. an
    ``xfail`` marker). That classification is a property of the generation
    algorithm's accessibles, not of a hand-built libcst statement, so this test
    verifies the representation-independent artifact instead: the
    :class:`ExceptionAssertion` the generator attaches for the raised exception.
    """
    module_name = "tests.fixtures.examples.unasserted_exceptions"
    config.configuration.module_name = module_name
    alias = get_module_alias(module_name)
    with install_import_hook(module_name, subject_properties):
        with subject_properties.instrumentation_tracer:
            module = importlib.import_module(module_name)
            importlib.reload(module)

        test_case = tc_factory(alias)
        suite = _suite(test_case)
        suite.accept(ag.AssertionGenerator(TestCaseExecutor(subject_properties)))

        assert _exception_assertion_names(test_case) == [expected_exception_name]
