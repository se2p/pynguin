#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides chromosome visitors to perform post-processing.

Statements are referenced by their index in the test case and inter-statement
dependencies are computed name-based via ``Statement.bound_variable`` /
``Statement.used_variables``.
"""

from __future__ import annotations

import abc
import logging
import math
from abc import ABC
from typing import TYPE_CHECKING

import pynguin.ga.chromosomevisitor as cv
import pynguin.ga.testcasechromosome as tcc
import pynguin.ga.testsuitechromosome as tsc
from pynguin.assertion.assertion import (
    Assertion,
    ExceptionAssertion,
    ReferenceAssertion,
)
from pynguin.utils.orderedset import OrderedSet

if TYPE_CHECKING:
    import pynguin.ga.computations as ff
    import pynguin.testcase.testcase as tc
    from pynguin.testcase.execution import SubprocessTestCaseExecutor

_LOGGER = logging.getLogger(__name__)


def get_assertion_protected_variables(test_case: tc.TestCase) -> set[str]:
    """Get the names of all variables that should be protected due to assertions.

    A variable name is protected if it is the source of a ``ReferenceAssertion`` or if
    it is in the (backward) dependency chain of such a variable.

    ``ExceptionAssertion`` are skipped (they have no source variable).

    Args:
        test_case: Test case to analyze

    Returns:
        Set of variable names that should not be removed during minimization.
    """
    protected = _directly_asserted_variables(test_case)
    if not protected:
        return protected
    _add_backward_dependencies(test_case, protected)
    return protected


def _directly_asserted_variables(test_case: tc.TestCase) -> set[str]:
    """Collect variable names that are the direct source of a reference assertion.

    Args:
        test_case: Test case to analyze.

    Returns:
        The set of directly asserted variable names.
    """
    protected: set[str] = set()
    for statement in test_case.statements():
        for assertion in statement.assertions:
            if isinstance(assertion, ExceptionAssertion):
                continue
            if isinstance(assertion, ReferenceAssertion):
                source = assertion.source
                # In the libcst representation the source is the variable name.
                if isinstance(source, str):
                    protected.add(source)
    return protected


def _add_backward_dependencies(test_case: tc.TestCase, protected: set[str]) -> None:
    """Extend *protected* with any variable used to compute a protected variable.

    Args:
        test_case: Test case to analyze.
        protected: The set of protected variable names, mutated in place.
    """
    statements = test_case.statements()
    changed = True
    while changed:
        changed = False
        for statement in statements:
            bv = statement.bound_variable
            if bv is not None and bv in protected:
                for used in statement.used_variables():
                    if used not in protected:
                        protected.add(used)
                        changed = True


class ExceptionTruncation(cv.ChromosomeVisitor):
    """Truncates test cases after an exception-raising statement."""

    def visit_test_suite_chromosome(  # noqa: D102
        self, chromosome: tsc.TestSuiteChromosome
    ) -> None:
        for test_case_chromosome in chromosome.test_case_chromosomes:
            test_case_chromosome.accept(self)

    def visit_test_case_chromosome(  # noqa: D102
        self, chromosome: tcc.TestCaseChromosome
    ) -> None:
        if chromosome.is_failing():
            chop_position = chromosome.get_last_mutatable_statement()
            if chop_position is not None:
                chromosome.test_case.chop(chop_position)


class AssertionMinimization(cv.ChromosomeVisitor):
    """Calculates the checked lines of each assertion.

    If an assertion does not cover new lines, it is removed from the resulting test
    case.
    """

    def __init__(self):  # noqa: D107
        self._remaining_assertions: OrderedSet[Assertion] = OrderedSet()
        self._deleted_assertions: OrderedSet[Assertion] = OrderedSet()
        self._checked_line_numbers: OrderedSet[int] = OrderedSet()

    @property
    def remaining_assertions(self) -> OrderedSet[Assertion]:
        """Provides a set of remaining assertions.

        Returns:
            The remaining assertions
        """
        return self._remaining_assertions

    @property
    def deleted_assertions(self) -> OrderedSet[Assertion]:
        """Provides a set of deleted assertions.

        Returns:
            The deleted assertions
        """
        return self._deleted_assertions

    def visit_test_suite_chromosome(  # noqa: D102
        self, chromosome: tsc.TestSuiteChromosome
    ) -> None:
        for test_case_chromosome in chromosome.test_case_chromosomes:
            test_case_chromosome.accept(self)

        _LOGGER.debug(
            f"Removed {len(self._deleted_assertions)} assertion(s) from "  # noqa: G004
            f"test suite that do not increase checked coverage",
        )

    def visit_test_case_chromosome(  # noqa: D102
        self, chromosome: tcc.TestCaseChromosome
    ) -> None:
        for statement in chromosome.test_case.statements():
            to_remove: OrderedSet[Assertion] = OrderedSet()
            for assertion in statement.assertions:
                new_checked_lines: OrderedSet[int] = OrderedSet()
                for instr in assertion.checked_instructions:
                    new_checked_lines.add(instr.lineno)  # type: ignore[arg-type]
                if (
                    # keep exception assertions to catch the exceptions
                    isinstance(assertion, ExceptionAssertion)
                    # keep assertions when they check "nothing", since this is
                    # more likely due to pyChecco's limitation, rather than an actual
                    # assertion that checks nothing at all
                    or not new_checked_lines
                    # keep assertions that increase checked coverage
                    or not new_checked_lines.issubset(self._checked_line_numbers)
                ):
                    self._checked_line_numbers.update(new_checked_lines)
                    self._remaining_assertions.add(assertion)
                else:
                    to_remove.add(assertion)
            for assertion in to_remove:
                statement.assertions.remove(assertion)
                self._deleted_assertions.add(assertion)


class TestCasePostProcessor(cv.ChromosomeVisitor):
    """Applies all given visitors to the visited test cases."""

    def __init__(  # noqa: D107
        self, test_case_visitors: list[ModificationAwareTestCaseVisitor]
    ):
        self._test_case_visitors = test_case_visitors

    def visit_test_suite_chromosome(  # noqa: D102
        self, chromosome: tsc.TestSuiteChromosome
    ) -> None:
        for test_case_chromosome in chromosome.test_case_chromosomes:
            test_case_chromosome.accept(self)

    def visit_test_case_chromosome(  # noqa: D102
        self, chromosome: tcc.TestCaseChromosome
    ) -> None:
        for visitor in self._test_case_visitors:
            visitor.visit_default_test_case(chromosome.test_case)
            # Remove the last execution result to force re-execution of the test case
            chromosome.remove_last_execution_result()


class ModificationAwareTestCaseVisitor(ABC):
    """Visitor that keeps information on modifications."""

    def __init__(self):  # noqa: D107
        self._deleted_statement_indexes: set[int] = set()

    @property
    def deleted_statement_indexes(self) -> set[int]:
        """Provides a set of deleted statement indexes.

        Returns:
            The deleted statement indexes
        """
        return self._deleted_statement_indexes

    @abc.abstractmethod
    def visit_default_test_case(self, test_case: tc.TestCase) -> None:
        """Visits and possibly modifies a test case.

        Args:
            test_case: The test case to process
        """


class IterativeMinimizationVisitor(ModificationAwareTestCaseVisitor):
    """Iteratively tries to remove statements while preserving fitness.

    For each statement in the test case:
    1. Create a clone of the test case
    2. Remove the statement from the clone and all dependent statements
    3. Execute the clone and calculate its fitness
    4. If fitness remains the same or improves, remove the statement from the original
    """

    def __init__(self, fitness_functions: OrderedSet[ff.TestSuiteCoverageFunction]):  # noqa: D107
        super().__init__()
        self._fitness_functions = fitness_functions
        self._removed_statements = 0

    @property
    def removed_statements(self) -> int:
        """Provides the number of removed statements.

        Returns:
            The number of removed statements
        """
        return self._removed_statements


def _coverages(
    fitness_functions: OrderedSet[ff.TestSuiteCoverageFunction],
    test_case: tc.TestCase,
) -> list[float]:
    suite = tsc.TestSuiteChromosome()
    suite.add_test_case_chromosome(tcc.TestCaseChromosome(test_case=test_case))
    return [ff_.compute_coverage(suite) for ff_ in fitness_functions]


class ForwardIterativeMinimizationVisitor(IterativeMinimizationVisitor):
    """Iteratively tries to remove statements (front to back) while preserving fitness."""

    def visit_default_test_case(self, test_case: tc.TestCase) -> None:  # noqa: D102
        original_coverages = _coverages(self._fitness_functions, test_case)
        original_size = test_case.size()
        protected = get_assertion_protected_variables(test_case)

        statements_changed = True
        while statements_changed:
            statements_changed = False
            i = 0
            while i < test_case.size():
                statement = test_case.get_statement(i)
                if statement.bound_variable in protected:
                    i += 1
                    continue
                test_clone = test_case.clone()
                test_clone.remove_statement_with_forward_dependencies(i)
                minimized_coverages = _coverages(self._fitness_functions, test_clone)
                if all(map(math.isclose, original_coverages, minimized_coverages)):
                    removed = test_case.remove_statement_with_forward_dependencies(i)
                    self._removed_statements += len(removed)
                    statements_changed = True
                else:
                    i += 1

        _LOGGER.debug(
            "Removed %s statement(s) from test case using forward iterative minimization",
            original_size - test_case.size(),
        )


class BackwardIterativeMinimizationVisitor(IterativeMinimizationVisitor):
    """Iteratively tries to remove statements (back to front) while preserving fitness."""

    def visit_default_test_case(self, test_case: tc.TestCase) -> None:  # noqa: D102
        original_coverages = _coverages(self._fitness_functions, test_case)
        original_size = test_case.size()
        protected = get_assertion_protected_variables(test_case)

        statements_changed = True
        while statements_changed and test_case.size() > 0:
            statements_changed = False
            i = test_case.size() - 1
            while i >= 0:
                statement = test_case.get_statement(i)
                if statement.bound_variable in protected:
                    i -= 1
                    continue
                test_clone = test_case.clone()
                test_clone.remove_statement_with_forward_dependencies(i)
                minimized_coverages = _coverages(self._fitness_functions, test_clone)
                if all(map(math.isclose, original_coverages, minimized_coverages)):
                    removed = test_case.remove_statement_with_forward_dependencies(i)
                    self._removed_statements += len(removed)
                    statements_changed = True
                    break
                i -= 1

        _LOGGER.debug(
            "Removed %s statement(s) from test case using backward iterative minimization",
            original_size - test_case.size(),
        )


class UnusedStatementsTestCaseVisitor(ModificationAwareTestCaseVisitor):
    """Removes unused primitive and collection statements (name-based)."""

    def visit_default_test_case(self, test_case: tc.TestCase) -> None:  # noqa: D102
        self._deleted_statement_indexes.clear()
        size_before = test_case.size()
        test_case.remove_unused_variables()
        _LOGGER.debug(
            "Removed %s unused primitives/collections from test case",
            size_before - test_case.size(),
        )


class TestSuiteMinimizationVisitor(cv.ChromosomeVisitor):
    """Minimizes a test suite by removing test cases that don't affect coverage."""

    def __init__(self, fitness_functions: OrderedSet[ff.TestSuiteCoverageFunction]):  # noqa: D107
        self._fitness_functions = fitness_functions
        self._removed_test_cases = 0

    @property
    def removed_test_cases(self) -> int:
        """Provides the number of removed test cases.

        Returns:
            The number of removed test cases
        """
        return self._removed_test_cases

    def visit_test_suite_chromosome(  # noqa: D102
        self, chromosome: tsc.TestSuiteChromosome
    ) -> None:
        if chromosome.size() <= 1:
            return

        original_coverage = [
            fitness_function.compute_coverage(chromosome)
            for fitness_function in self._fitness_functions
        ]

        test_cases = list(chromosome.test_case_chromosomes)
        i = 0
        while i < len(test_cases):
            if len(test_cases) == 1:
                break

            test_suite_clone = chromosome.clone()
            test_to_remove = test_suite_clone.get_test_case_chromosome(i)
            test_suite_clone.delete_test_case_chromosome(test_to_remove)

            minimized_coverage = [
                fitness_function.compute_coverage(test_suite_clone)
                for fitness_function in self._fitness_functions
            ]

            if all(map(math.isclose, original_coverage, minimized_coverage)):
                chromosome.delete_test_case_chromosome(test_cases[i])
                test_cases.pop(i)
                self._removed_test_cases += 1
            else:
                i += 1

        if self._removed_test_cases > 0:
            chromosome.changed = True

    def visit_test_case_chromosome(  # noqa: D102
        self, chromosome: tcc.TestCaseChromosome
    ) -> None:
        # Nothing to do for individual test cases
        pass


class CrashPreservingMinimizationVisitor(ModificationAwareTestCaseVisitor):
    """Iteratively tries to remove statements while preserving crash behavior."""

    def __init__(self, executor: SubprocessTestCaseExecutor):  # noqa: D107
        super().__init__()
        self._executor = executor
        self._removed_statements = 0

    @property
    def removed_statements(self) -> int:
        """Provides the number of removed statements.

        Returns:
            The number of removed statements
        """
        return self._removed_statements

    def visit_default_test_case(self, test_case: tc.TestCase) -> None:  # noqa: D102
        original_size = test_case.size()
        if test_case.size() == 0:
            return

        statements_changed = True
        while statements_changed:
            statements_changed = False
            i = 0
            while i < test_case.size():
                test_clone = test_case.clone()
                test_clone.remove_statement_with_forward_dependencies(i)

                exit_code = self._executor.execute_with_exit_code(test_clone)
                if exit_code != 0:
                    removed = test_case.remove_statement_with_forward_dependencies(i)
                    self._removed_statements += len(removed)
                    statements_changed = True
                else:
                    i += 1

        _LOGGER.debug(
            "Removed %s statement(s) from crashed test case using crash-preserving minimization",
            original_size - test_case.size(),
        )


class CombinedMinimizationVisitor(cv.ChromosomeVisitor):
    """Combines test suite and test case minimization for optimal results."""

    def __init__(self, fitness_functions: OrderedSet[ff.TestSuiteCoverageFunction]):  # noqa: D107
        self._fitness_functions = fitness_functions
        self._removed_statements = 0

    @property
    def removed_statements(self) -> int:
        """Provides the number of removed statements.

        Returns:
            The number of removed statements
        """
        return self._removed_statements

    def visit_test_suite_chromosome(  # noqa: D102
        self, chromosome: tsc.TestSuiteChromosome
    ) -> None:
        original_coverage = [
            fitness_function.compute_coverage(chromosome)
            for fitness_function in self._fitness_functions
        ]
        self._minimize_statements_across_test_suite(chromosome, original_coverage)
        if self._removed_statements > 0:
            chromosome.changed = True

    def visit_test_case_chromosome(  # noqa: D102
        self, chromosome: tcc.TestCaseChromosome
    ) -> None:
        # Nothing to do for individual test cases
        pass

    def _minimize_statements_across_test_suite(
        self, chromosome: tsc.TestSuiteChromosome, original_coverage: list[float]
    ) -> None:
        statements_changed = True
        while statements_changed:
            statements_changed = False
            for test_case_idx, test_case_chrom in enumerate(chromosome.test_case_chromosomes):
                test_case = test_case_chrom.test_case
                i = 0
                while i < test_case.size():
                    test_suite_clone = chromosome.clone()
                    clone_test_case_chrom: tcc.TestCaseChromosome = (
                        test_suite_clone.get_test_case_chromosome(test_case_idx)
                    )
                    clone_test_case = clone_test_case_chrom.test_case
                    clone_test_case.remove_statement_with_forward_dependencies(i)
                    test_suite_clone.set_test_case_chromosome(
                        test_case_idx, tcc.TestCaseChromosome(clone_test_case)
                    )

                    minimized_coverages = [
                        fitness_function.compute_coverage(test_suite_clone)
                        for fitness_function in self._fitness_functions
                    ]

                    if all(map(math.isclose, original_coverage, minimized_coverages)):
                        removed = test_case.remove_statement_with_forward_dependencies(i)
                        self._removed_statements += len(removed)
                        chromosome.set_test_case_chromosome(
                            test_case_idx, tcc.TestCaseChromosome(test_case)
                        )
                        statements_changed = True
                    else:
                        i += 1

            if not statements_changed:
                break


class EmptyTestCaseRemover(cv.ChromosomeVisitor):
    """Removes empty test cases from a test suite."""

    def __init__(self):  # noqa: D107
        self._removed_test_cases = 0

    @property
    def removed_test_cases(self) -> int:
        """Provides the number of removed test cases.

        Returns:
            The number of removed test cases
        """
        return self._removed_test_cases

    def visit_test_suite_chromosome(  # noqa: D102
        self, chromosome: tsc.TestSuiteChromosome
    ) -> None:
        original_size = chromosome.size()
        chromosome.test_case_chromosomes = [
            test for test in chromosome.test_case_chromosomes if test.size() > 0
        ]
        self._removed_test_cases = original_size - chromosome.size()
        if self._removed_test_cases > 0:
            chromosome.changed = True
            _LOGGER.info("Removed %d empty test case(s) from test suite", self._removed_test_cases)

    def visit_test_case_chromosome(  # noqa: D102
        self, chromosome: tcc.TestCaseChromosome
    ) -> None:
        # Nothing to do for individual test cases
        pass
