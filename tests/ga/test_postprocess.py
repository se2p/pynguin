#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Tests for the libcst-based post-processing visitors.

Statements/test cases are built via the ``tests/testcase/_builders.py`` helpers instead
of the removed per-statement representation, and fitness/coverage functions are plain
``MagicMock`` doubles, matching how the visitors under test only rely on a duck-typed
``compute_coverage`` method.
"""

from unittest.mock import MagicMock, call

import pytest

import pynguin.ga.postprocess as pp
import pynguin.ga.testcasechromosome as tcc
import pynguin.ga.testsuitechromosome as tsc
import pynguin.testcase.testcase as tc
from pynguin.assertion.assertion import ExceptionAssertion, ObjectAssertion, ReferenceAssertion
from pynguin.ga.computations import TestSuiteBranchCoverageFunction, TestSuiteLineCoverageFunction
from pynguin.testcase.execution import SubprocessTestCaseExecutor
from pynguin.utils.orderedset import OrderedSet
from tests.testcase._builders import assign, float_stmt, int_stmt, make_test_case, str_stmt

# -- get_assertion_protected_variables & helpers --------------------------------------


def test_get_assertion_protected_variables_no_assertions():
    test_case = make_test_case(int_stmt("int_0", 1))
    assert pp.get_assertion_protected_variables(test_case) == set()


@pytest.mark.parametrize(
    "make_assertion,expect_protected",
    [
        (lambda: ObjectAssertion("int_0", 1), True),
        (lambda: MagicMock(spec=ExceptionAssertion), False),
        (lambda: MagicMock(spec=ReferenceAssertion, source=123), False),
    ],
    ids=["reference_assertion", "exception_assertion_skipped", "non_str_source_skipped"],
)
def test_directly_asserted_variables(make_assertion, expect_protected):
    statement = int_stmt("int_0", 1)
    statement.assertions.append(make_assertion())
    test_case = make_test_case(statement)

    result = pp.get_assertion_protected_variables(test_case)

    assert ("int_0" in result) is expect_protected


def test_backward_dependencies_are_transitively_protected():
    root = int_stmt("int_0", 1)
    middle = assign("int_1", "int_0 + 1", bound_type=int)
    leaf = assign("int_2", "int_1 + 1", bound_type=int)
    leaf.assertions.append(ObjectAssertion("int_2", 3))
    test_case = make_test_case(root, middle, leaf)

    result = pp.get_assertion_protected_variables(test_case)

    assert result == {"int_0", "int_1", "int_2"}


def test_backward_dependencies_do_not_protect_unrelated_variables():
    unrelated = int_stmt("int_0", 1)
    asserted = int_stmt("int_1", 2)
    asserted.assertions.append(ObjectAssertion("int_1", 2))
    test_case = make_test_case(unrelated, asserted)

    result = pp.get_assertion_protected_variables(test_case)

    assert result == {"int_1"}


# -- AssertionMinimization -------------------------------------------------------------


def test_assertion_minimization_visits_every_test_case_in_suite():
    ass_min = pp.AssertionMinimization()
    chromosome = MagicMock()
    suite = MagicMock(test_case_chromosomes=[chromosome, chromosome])

    ass_min.visit_test_suite_chromosome(suite)

    chromosome.accept.assert_has_calls([call(ass_min), call(ass_min)])


@pytest.mark.parametrize(
    "make_assertions,expected_remaining,expected_deleted",
    [
        (
            lambda: [
                MagicMock(checked_instructions=[MagicMock(lineno=1), MagicMock(lineno=2)]),
                MagicMock(checked_instructions=[MagicMock(lineno=1)]),
            ],
            [0],
            [1],
        ),
        (
            lambda: [
                MagicMock(checked_instructions=[MagicMock(lineno=1)]),
                MagicMock(spec=ExceptionAssertion, checked_instructions=[MagicMock(lineno=1)]),
            ],
            [0, 1],
            [],
        ),
        (
            lambda: [MagicMock(checked_instructions=[])],
            [0],
            [],
        ),
    ],
    ids=["subset_of_checked_lines_removed", "exception_assertion_kept", "empty_checked_kept"],
)
def test_assertion_minimization_test_case(make_assertions, expected_remaining, expected_deleted):
    ass_min = pp.AssertionMinimization()
    statement = int_stmt("int_0", 1)
    assertions = make_assertions()
    statement.assertions.extend(assertions)
    test_case = make_test_case(statement)
    chromosome = tcc.TestCaseChromosome(test_case=test_case)

    ass_min.visit_test_case_chromosome(chromosome)

    assert ass_min.remaining_assertions == OrderedSet([assertions[i] for i in expected_remaining])
    assert ass_min.deleted_assertions == OrderedSet([assertions[i] for i in expected_deleted])
    assert test_case.get_assertions() == [assertions[i] for i in expected_remaining]


# -- UnusedStatementsTestCaseVisitor ----------------------------------------------------


def test_unused_statements_visitor_turns_unused_assignment_into_expression():
    kept = int_stmt("int_0", 1)
    unused = assign("int_1", "int_0 + 1", bound_type=int)
    test_case = make_test_case(kept, unused)
    visitor = pp.UnusedStatementsTestCaseVisitor()

    visitor.visit_default_test_case(test_case)

    # remove_unused_variables never drops statements outright; it strips the binding.
    assert test_case.size() == 2
    assert test_case.get_statement(0).bound_variable == "int_0"
    assert test_case.get_statement(1).bound_variable is None
    assert visitor.deleted_statement_indexes == set()


# -- Forward/Backward IterativeMinimizationVisitor --------------------------------------


@pytest.fixture
def branch_fitness_function():
    return MagicMock(spec=TestSuiteBranchCoverageFunction)


@pytest.mark.parametrize(
    "visitor_class",
    [pp.ForwardIterativeMinimizationVisitor, pp.BackwardIterativeMinimizationVisitor],
    ids=["forward", "backward"],
)
def test_iterative_minimization_visitor_empty_test_case(visitor_class, branch_fitness_function):
    branch_fitness_function.compute_coverage.return_value = 0.0
    test_case = tc.TestCase()
    visitor = visitor_class(OrderedSet([branch_fitness_function]))

    visitor.visit_default_test_case(test_case)

    assert visitor.removed_statements == 0
    assert test_case.size() == 0
    assert visitor.deleted_statement_indexes == set()


@pytest.mark.parametrize(
    "visitor_class",
    [pp.ForwardIterativeMinimizationVisitor, pp.BackwardIterativeMinimizationVisitor],
    ids=["forward", "backward"],
)
@pytest.mark.parametrize(
    "coverage_side_effect,expected_removed,expected_size",
    [
        (lambda _suite: 1.0, 2, 0),
        (
            lambda suite: (1.0 if suite.test_case_chromosomes[0].test_case.size() == 2 else 0.5),
            0,
            2,
        ),
    ],
    ids=["fitness_preserved", "fitness_reduced"],
)
def test_iterative_minimization_visitor_statement_removal(
    visitor_class,
    coverage_side_effect,
    expected_removed,
    expected_size,
    branch_fitness_function,
):
    branch_fitness_function.compute_coverage.side_effect = coverage_side_effect
    test_case = make_test_case(int_stmt("int_0", 1), float_stmt("float_0", 1.5))
    visitor = visitor_class(OrderedSet([branch_fitness_function]))

    visitor.visit_default_test_case(test_case)

    assert visitor.removed_statements == expected_removed
    assert test_case.size() == expected_size


@pytest.mark.parametrize(
    "visitor_class",
    [pp.ForwardIterativeMinimizationVisitor, pp.BackwardIterativeMinimizationVisitor],
    ids=["forward", "backward"],
)
def test_iterative_minimization_visitor_skips_protected_statements(
    visitor_class, branch_fitness_function
):
    # int_0 is protected via an assertion; coverage never changes, so only the
    # unprotected int_1 may be removed.
    protected = int_stmt("int_0", 1)
    protected.assertions.append(ObjectAssertion("int_0", 1))
    removable = int_stmt("int_1", 2)
    test_case = make_test_case(protected, removable)
    branch_fitness_function.compute_coverage.return_value = 1.0
    visitor = visitor_class(OrderedSet([branch_fitness_function]))

    visitor.visit_default_test_case(test_case)

    assert visitor.removed_statements == 1
    assert test_case.size() == 1
    assert test_case.get_statement(0).bound_variable == "int_0"


@pytest.mark.parametrize(
    "visitor_class",
    [pp.ForwardIterativeMinimizationVisitor, pp.BackwardIterativeMinimizationVisitor],
    ids=["forward", "backward"],
)
def test_iterative_minimization_visitor_preserves_forward_dependencies(
    visitor_class, branch_fitness_function
):
    test_case = make_test_case(
        int_stmt("int_0", 1),
        assign("list_0", "[int_0]", bound_type=list),
        str_stmt("str_0", "unused"),
    )

    def coverage(suite):
        names = {s.bound_variable for s in suite.test_case_chromosomes[0].test_case.statements()}
        return 1.0 if {"int_0", "list_0"} <= names else 0.5

    branch_fitness_function.compute_coverage.side_effect = coverage
    visitor = visitor_class(OrderedSet([branch_fitness_function]))

    visitor.visit_default_test_case(test_case)

    assert visitor.removed_statements == 1
    assert test_case.size() == 2
    names = {s.bound_variable for s in test_case.statements()}
    assert names == {"int_0", "list_0"}


# -- TestSuiteMinimizationVisitor -------------------------------------------------------


@pytest.fixture
def line_fitness_function():
    return MagicMock(spec=TestSuiteLineCoverageFunction)


def test_test_suite_minimization_visitor_init(line_fitness_function):
    fitness_functions = OrderedSet([line_fitness_function])
    visitor = pp.TestSuiteMinimizationVisitor(fitness_functions)

    assert visitor._fitness_functions == fitness_functions
    assert visitor.removed_test_cases == 0


def test_test_suite_minimization_visitor_test_case_chromosome_is_noop():
    visitor = pp.TestSuiteMinimizationVisitor(OrderedSet([MagicMock()]))
    visitor.visit_test_case_chromosome(MagicMock())  # no-op, must not raise


def test_test_suite_minimization_visitor_single_test_case(line_fitness_function):
    line_fitness_function.compute_coverage.return_value = 1.0
    suite = tsc.TestSuiteChromosome()
    suite.add_test_case_chromosome(
        tcc.TestCaseChromosome(test_case=make_test_case(int_stmt("int_0", 1)))
    )
    visitor = pp.TestSuiteMinimizationVisitor(OrderedSet([line_fitness_function]))

    visitor.visit_test_suite_chromosome(suite)

    assert visitor.removed_test_cases == 0
    assert suite.size() == 1


@pytest.mark.parametrize(
    "coverage_side_effect,expected_removed,expected_size",
    [
        (lambda _suite: 1.0, 1, 1),
        (lambda suite: 1.0 if suite.size() == 2 else 0.5, 0, 2),
    ],
    ids=["fitness_preserved", "fitness_reduced"],
)
def test_test_suite_minimization_visitor_removal(
    coverage_side_effect, expected_removed, expected_size, line_fitness_function
):
    line_fitness_function.compute_coverage.side_effect = coverage_side_effect
    suite = tsc.TestSuiteChromosome()
    suite.add_test_case_chromosome(
        tcc.TestCaseChromosome(test_case=make_test_case(int_stmt("int_0", 1)))
    )
    suite.add_test_case_chromosome(
        tcc.TestCaseChromosome(test_case=make_test_case(int_stmt("int_0", 1)))
    )
    visitor = pp.TestSuiteMinimizationVisitor(OrderedSet([line_fitness_function]))

    visitor.visit_test_suite_chromosome(suite)

    assert visitor.removed_test_cases == expected_removed
    assert suite.size() == expected_size


# -- CrashPreservingMinimizationVisitor --------------------------------------------------


@pytest.fixture
def mock_executor():
    return MagicMock(spec=SubprocessTestCaseExecutor)


def test_crash_preserving_minimization_visitor_init(mock_executor):
    visitor = pp.CrashPreservingMinimizationVisitor(mock_executor)

    assert visitor._executor is mock_executor
    assert visitor.removed_statements == 0
    assert visitor.deleted_statement_indexes == set()


def test_crash_preserving_minimization_visitor_empty_test_case(mock_executor):
    visitor = pp.CrashPreservingMinimizationVisitor(mock_executor)
    test_case = tc.TestCase()

    visitor.visit_default_test_case(test_case)

    assert visitor.removed_statements == 0
    assert test_case.size() == 0
    mock_executor.execute_with_exit_code.assert_not_called()


@pytest.mark.parametrize(
    "exit_codes,expected_removed,expected_size",
    [
        ([-11, -11], 2, 0),
        ([0, 0], 0, 2),
        ([-11, 0, 0], 1, 1),
    ],
    ids=["all_crash", "none_crash", "mixed_results"],
)
def test_crash_preserving_minimization_visitor_statement_removal(
    mock_executor, exit_codes, expected_removed, expected_size
):
    mock_executor.execute_with_exit_code.side_effect = exit_codes
    test_case = make_test_case(int_stmt("int_0", 1), int_stmt("int_1", 2))
    visitor = pp.CrashPreservingMinimizationVisitor(mock_executor)

    visitor.visit_default_test_case(test_case)

    assert visitor.removed_statements == expected_removed
    assert test_case.size() == expected_size


# -- CombinedMinimizationVisitor ---------------------------------------------------------


def test_combined_minimization_visitor_init(line_fitness_function):
    fitness_functions = OrderedSet([line_fitness_function])
    visitor = pp.CombinedMinimizationVisitor(fitness_functions)

    assert visitor._fitness_functions == fitness_functions
    assert visitor.removed_statements == 0


def test_combined_minimization_visitor_test_case_chromosome_is_noop():
    visitor = pp.CombinedMinimizationVisitor(OrderedSet([MagicMock()]))
    visitor.visit_test_case_chromosome(MagicMock())  # no-op, must not raise


def _two_test_case_suite() -> tsc.TestSuiteChromosome:
    suite = tsc.TestSuiteChromosome()
    for _ in range(2):
        suite.add_test_case_chromosome(
            tcc.TestCaseChromosome(
                test_case=make_test_case(int_stmt("int_0", 1), float_stmt("float_0", 1.5))
            )
        )
    return suite


@pytest.mark.parametrize(
    "coverage_side_effect,expected_removed",
    [
        (lambda _suite: 1.0, 4),
        ("use_counter", 0),
    ],
    ids=["fitness_preserved", "fitness_changed"],
)
def test_combined_minimization_visitor_minimization(
    coverage_side_effect, expected_removed, line_fitness_function
):
    if coverage_side_effect == "use_counter":
        call_count = [0]

        def side_effect(_suite):
            call_count[0] += 1
            return 1.0 if call_count[0] == 1 else 0.0

        line_fitness_function.compute_coverage.side_effect = side_effect
    else:
        line_fitness_function.compute_coverage.side_effect = coverage_side_effect

    suite = _two_test_case_suite()
    visitor = pp.CombinedMinimizationVisitor(OrderedSet([line_fitness_function]))

    visitor.visit_test_suite_chromosome(suite)

    assert visitor.removed_statements == expected_removed


def test_combined_minimization_visitor_single_test_case(line_fitness_function):
    call_count = [0]

    def side_effect(_suite):
        call_count[0] += 1
        return 1.0 if call_count[0] == 1 else 0.5

    line_fitness_function.compute_coverage.side_effect = side_effect
    suite = tsc.TestSuiteChromosome()
    suite.add_test_case_chromosome(
        tcc.TestCaseChromosome(
            test_case=make_test_case(int_stmt("int_0", 1), float_stmt("float_0", 1.5))
        )
    )
    visitor = pp.CombinedMinimizationVisitor(OrderedSet([line_fitness_function]))

    visitor.visit_test_suite_chromosome(suite)

    assert suite.size() == 1


# -- EmptyTestCaseRemover ----------------------------------------------------------------


def test_empty_test_case_remover_test_case_chromosome_is_noop():
    remover = pp.EmptyTestCaseRemover()
    remover.visit_test_case_chromosome(MagicMock())  # no-op, must not raise


def test_empty_test_case_remover_removes_only_empty_test_cases():
    remover = pp.EmptyTestCaseRemover()
    suite = tsc.TestSuiteChromosome()
    suite.add_test_case_chromosome(
        tcc.TestCaseChromosome(test_case=make_test_case(int_stmt("int_0", 1)))
    )
    suite.add_test_case_chromosome(tcc.TestCaseChromosome(test_case=tc.TestCase()))

    remover.visit_test_suite_chromosome(suite)

    assert remover.removed_test_cases == 1
    assert suite.size() == 1
