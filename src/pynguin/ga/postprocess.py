#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides chromosome visitors to perform post-processing."""

from __future__ import annotations

import abc
import logging
import math

from abc import ABC
from typing import TYPE_CHECKING

import pynguin.ga.chromosomevisitor as cv
import pynguin.ga.testcasechromosome as tcc
import pynguin.ga.testsuitechromosome as tsc
import pynguin.testcase.testcase as tc
import pynguin.testcase.testcasevisitor as tcv

from pynguin.assertion.assertion import Assertion
from pynguin.assertion.assertion import ExceptionAssertion
from pynguin.testcase.statement import StatementVisitor
from pynguin.utils.orderedset import OrderedSet


if TYPE_CHECKING:
    import pynguin.ga.computations as ff

    from pynguin.testcase.execution import SubprocessTestCaseExecutor

_LOGGER = logging.getLogger(__name__)


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
        for stmt in chromosome.test_case.statements:
            to_remove: OrderedSet[Assertion] = OrderedSet()
            for assertion in stmt.assertions:
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
                stmt.assertions.remove(assertion)
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
            chromosome.test_case.accept(visitor)
            # Remove the last execution result to force re-execution of the test case
            chromosome.remove_last_execution_result()


class ModificationAwareTestCaseVisitor(tcv.TestCaseVisitor, ABC):
    """Visitor that keep information on modifications."""

    def __init__(self):  # noqa: D107
        self._deleted_statement_indexes: set[int] = set()

    @property
    def deleted_statement_indexes(self) -> set[int]:
        """Provides a set of deleted statement indexes.

        Returns:
            The deleted statement indexes
        """
        return self._deleted_statement_indexes


class IterativeMinimizationVisitor(ModificationAwareTestCaseVisitor):
    """Iteratively tries to remove statements while preserving fitness.

    For each statement in the test case:
    1. Create a clone of the test case
    2. Remove the statement from the clone and all dependent statements
    3. Execute the clone and calculate its fitness
    4. If fitness remains the same or improves, remove the statement from the original test case
    """

    def __init__(self, fitness_function: ff.TestSuiteCoverageFunction):  # noqa: D107
        super().__init__()
        self._fitness_function = fitness_function
        self._removed_statements = 0

    @property
    def removed_statements(self) -> int:
        """Provides the number of removed statements.

        Returns:
            The number of removed statements
        """
        return self._removed_statements

    @abc.abstractmethod
    def visit_default_test_case(self, test_case: tc.TestCase) -> None:
        """Visits a test case and tries to minimize it.

        Args:
            test_case: The test case to minimize
        """


class ForwardIterativeMinimizationVisitor(IterativeMinimizationVisitor):
    """Iteratively tries to remove statements while preserving fitness.

    Iterates front to back (forward) and uses forward dependencies when removing statements.

    For each statement in the test case:
    1. Create a clone of the test case
    2. Remove the statement from the clone and all forward dependent statements
    3. Execute the clone and calculate its fitness
    4. If fitness remains the same or improves, remove the statement from the original test case
    """

    def visit_default_test_case(self, test_case: tc.TestCase) -> None:  # noqa: D102
        original_test_case = tcc.TestCaseChromosome(test_case=test_case)
        original_test_suite = tsc.TestSuiteChromosome()
        original_test_suite.add_test_case_chromosome(original_test_case)
        original_coverage = self._fitness_function.compute_coverage(original_test_suite)

        original_size = test_case.size()
        statements_changed = True

        while statements_changed:
            statements_changed = False
            statements = list(test_case.statements)

            i = 0
            while i < len(statements):
                stmt = statements[i]
                if stmt.get_position() >= test_case.size():
                    break

                test_clone = test_case.clone()
                clone_stmt = test_clone.get_statement(stmt.get_position())
                test_clone.remove_statement_with_forward_dependencies(clone_stmt)
                minimized_test_case = tcc.TestCaseChromosome(test_case=test_clone)
                minimized_test_suite = tsc.TestSuiteChromosome()
                minimized_test_suite.add_test_case_chromosome(minimized_test_case)
                minimized_coverage = self._fitness_function.compute_coverage(minimized_test_suite)
                if math.isclose(original_coverage, minimized_coverage):
                    removed = test_case.remove_statement_with_forward_dependencies(stmt)
                    self._removed_statements += len(removed)

                    # Update the statements list to reflect the changes in the test case
                    statements = list(test_case.statements)
                    # Don't increment i since we've removed elements and the list has shifted
                    statements_changed = True
                else:
                    i += 1

            if not statements_changed:
                break

        _LOGGER.debug(
            "Removed %s statement(s) from test case using forward iterative minimization",
            original_size - test_case.size(),
        )


class BackwardIterativeMinimizationVisitor(IterativeMinimizationVisitor):
    """Iteratively tries to remove statements while preserving fitness.

    Iterates back to front (backward) and uses backward dependencies when removing statements.

    For each statement in the test case:
    1. Create a clone of the test case
    2. Remove the statement from the clone and all backward dependent statements
    3. Execute the clone and calculate its fitness
    4. If fitness remains the same or improves, remove the statement from the original test case
    """

    def visit_default_test_case(self, test_case: tc.TestCase) -> None:  # noqa: D102
        original_test_case = tcc.TestCaseChromosome(test_case=test_case)
        original_test_suite = tsc.TestSuiteChromosome()
        original_test_suite.add_test_case_chromosome(original_test_case)
        original_coverage = self._fitness_function.compute_coverage(original_test_suite)

        original_size = test_case.size()
        statements_changed = True

        while statements_changed and test_case.size() > 0:
            statements_changed = False

            i = test_case.size() - 1
            while 0 <= i < test_case.size():
                stmt = test_case.get_statement(i)
                test_clone = test_case.clone()
                clone_stmt = test_clone.get_statement(i)
                test_clone.remove_statement_with_forward_dependencies(clone_stmt)
                minimized_test_case = tcc.TestCaseChromosome(test_case=test_clone)
                minimized_test_suite = tsc.TestSuiteChromosome()
                minimized_test_suite.add_test_case_chromosome(minimized_test_case)
                minimized_coverage = self._fitness_function.compute_coverage(minimized_test_suite)
                if math.isclose(original_coverage, minimized_coverage):
                    removed = test_case.remove_statement_with_forward_dependencies(stmt)
                    self._removed_statements += len(removed)
                    statements_changed = True
                    break
                i -= 1

        _LOGGER.debug(
            "Removed %s statement(s) from test case using backward iterative minimization",
            original_size - test_case.size(),
        )


class UnusedStatementsTestCaseVisitor(ModificationAwareTestCaseVisitor):
    """Removes unused primitive and collection statements."""

    def visit_default_test_case(self, test_case) -> None:  # noqa: D102
        self._deleted_statement_indexes.clear()
        primitive_remover = UnusedPrimitiveOrCollectionStatementVisitor()
        size_before = test_case.size()
        # Iterate over copy, to be able to modify original.
        for stmt in reversed(list(test_case.statements)):
            stmt.accept(primitive_remover)
        _LOGGER.debug(
            "Removed %s unused primitives/collections from test case",
            size_before - test_case.size(),
        )
        self._deleted_statement_indexes.update(primitive_remover.deleted_statement_indexes)


class UnusedPrimitiveOrCollectionStatementVisitor(StatementVisitor):  # noqa: PLR0904
    """Visits all statements and removes the unused primitives and collections.

    Has to visit the statements in reverse order.
    """

    def __init__(self):  # noqa: D107
        self._used_references = set()
        self._deleted_statement_indexes: set[int] = set()

    @property
    def deleted_statement_indexes(self) -> set[int]:
        """Provides a set of deleted statement indexes.

        Returns:
            The deleted statement indexes
        """
        return self._deleted_statement_indexes

    def _handle_collection_or_primitive(self, stmt) -> None:
        if stmt.ret_val in self._used_references:
            self._handle_remaining(stmt)
        else:
            self._deleted_statement_indexes.add(stmt.get_position())
            stmt.test_case.remove_statement(stmt)

    def _handle_remaining(self, stmt) -> None:
        used = stmt.get_variable_references()
        used.discard(stmt.ret_val)
        self._used_references.update(used)

    def visit_int_primitive_statement(self, stmt) -> None:  # noqa: D102
        self._handle_collection_or_primitive(stmt)

    def visit_float_primitive_statement(self, stmt) -> None:  # noqa: D102
        self._handle_collection_or_primitive(stmt)

    def visit_complex_primitive_statement(self, stmt) -> None:  # noqa: D102
        self._handle_collection_or_primitive(stmt)

    def visit_string_primitive_statement(self, stmt) -> None:  # noqa: D102
        self._handle_collection_or_primitive(stmt)

    def visit_bytes_primitive_statement(self, stmt) -> None:  # noqa: D102
        self._handle_collection_or_primitive(stmt)

    def visit_boolean_primitive_statement(self, stmt) -> None:  # noqa: D102
        self._handle_collection_or_primitive(stmt)

    def visit_enum_statement(self, stmt) -> None:  # noqa: D102
        self._handle_collection_or_primitive(stmt)

    def visit_class_primitive_statement(self, stmt) -> None:  # noqa: D102
        self._handle_collection_or_primitive(stmt)

    def visit_none_statement(self, stmt) -> None:  # noqa: D102
        self._handle_collection_or_primitive(stmt)

    def visit_constructor_statement(self, stmt) -> None:  # noqa: D102
        self._handle_remaining(stmt)

    def visit_method_statement(self, stmt) -> None:  # noqa: D102
        self._handle_remaining(stmt)

    def visit_function_statement(self, stmt) -> None:  # noqa: D102
        self._handle_remaining(stmt)

    def visit_field_statement(self, stmt) -> None:  # noqa: D102
        raise NotImplementedError("No field support yet.")

    def visit_assignment_statement(self, stmt) -> None:  # noqa: D102
        raise NotImplementedError("No field support yet.")

    def visit_list_statement(self, stmt) -> None:  # noqa: D102
        self._handle_collection_or_primitive(stmt)

    def visit_ndarray_statement(self, stmt) -> None:  # noqa: D102
        self._handle_collection_or_primitive(stmt)

    def visit_allowed_values_statement(self, stmt) -> None:  # noqa: D102
        self._handle_collection_or_primitive(stmt)

    def visit_set_statement(self, stmt) -> None:  # noqa: D102
        self._handle_collection_or_primitive(stmt)

    def visit_tuple_statement(self, stmt) -> None:  # noqa: D102
        self._handle_collection_or_primitive(stmt)

    def visit_dict_statement(self, stmt) -> None:  # noqa: D102
        self._handle_collection_or_primitive(stmt)

    def visit_ast_assign_statement(self, stmt) -> None:  # noqa: D102
        self._handle_remaining(stmt)


class TestSuiteMinimizationVisitor(cv.ChromosomeVisitor):
    """Minimizes a test suite by removing test cases that don't affect coverage.

    For each test case in the test suite:
    1. Create a clone of the test suite
    2. Remove the test case from the clone
    3. Execute the clone and calculate its fitness
    4. If fitness remains the same, remove the test case from the original test suite
    """

    def __init__(self, fitness_function: ff.TestSuiteCoverageFunction):  # noqa: D107
        self._fitness_function = fitness_function
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
            # Nothing to minimize if there's only one or zero test cases
            return

        original_coverage = self._fitness_function.compute_coverage(chromosome)

        test_cases = list(chromosome.test_case_chromosomes)
        i = 0

        while i < len(test_cases):
            # Always keep at least one test case
            if len(test_cases) == 1:
                break

            test_suite_clone = chromosome.clone()
            test_to_remove = test_suite_clone.get_test_case_chromosome(i)
            test_suite_clone.delete_test_case_chromosome(test_to_remove)

            minimized_coverage = self._fitness_function.compute_coverage(test_suite_clone)

            # If coverage is not affected, remove the test case from the original test suite
            if math.isclose(original_coverage, minimized_coverage):
                chromosome.delete_test_case_chromosome(test_cases[i])
                # Update our working list
                test_cases.pop(i)
                self._removed_test_cases += 1
                # Don't increment i since we've removed an element and the list has shifted
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
    """Iteratively tries to remove statements while preserving crash behavior.

    For each statement in the test case:
    1. Create a clone of the test case
    2. Remove the statement from the clone and all forward dependent statements
    3. Execute the clone and check if it still crashes
    4. If it still crashes, remove the statement from the original test case
    """

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

        # Skip if the test case is empty
        if test_case.size() == 0:
            return

        statements_changed = True

        while statements_changed:
            statements_changed = False
            statements = list(test_case.statements)

            i = 0
            while i < len(statements):
                stmt = statements[i]
                if stmt.get_position() >= test_case.size():
                    break

                test_clone = test_case.clone()
                clone_stmt = test_clone.get_statement(stmt.get_position())
                test_clone.remove_statement_with_forward_dependencies(clone_stmt)

                # Execute the clone and check if it still crashes
                exit_code = self._executor.execute_with_exit_code(test_clone)

                if exit_code != 0:
                    # If the clone still crashes, remove the statement from the original test case
                    removed = test_case.remove_statement_with_forward_dependencies(stmt)
                    self._removed_statements += len(removed)

                    # Update the statements list to reflect the changes in the test case
                    statements = list(test_case.statements)
                    # Don't increment i since we've removed elements and the list has shifted
                    statements_changed = True
                else:
                    i += 1

            if not statements_changed:
                break

        _LOGGER.debug(
            "Removed %s statement(s) from crashed test case using crash-preserving minimization",
            original_size - test_case.size(),
        )


class CombinedMinimizationVisitor(cv.ChromosomeVisitor):
    """Combines test suite and test case minimization for optimal results.

    This visitor applies a combined approach that minimizes both test cases and the test suite
    by checking statements against the entire test suite coverage:

    For each statement in each test case:
       a. Create a clone of the entire test suite
       b. Remove the statement from the clone
       c. Compute the coverage of the modified test suite
       d. If the coverage doesn't decrease, remove the statement from the original test case
    """

    def __init__(self, fitness_function: ff.TestSuiteCoverageFunction):  # noqa: D107
        self._fitness_function = fitness_function
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
        original_coverage = self._fitness_function.compute_coverage(chromosome)
        self._minimize_statements_across_test_suite(chromosome, original_coverage)
        if self._removed_statements > 0:
            chromosome.changed = True

    def visit_test_case_chromosome(  # noqa: D102
        self, chromosome: tcc.TestCaseChromosome
    ) -> None:
        # Nothing to do for individual test cases
        pass

    def _minimize_statements_across_test_suite(
        self, chromosome: tsc.TestSuiteChromosome, original_coverage: float
    ) -> None:
        """Minimize statements across the entire test suite.

        Args:
            chromosome: The test suite to minimize
            original_coverage: The original coverage to preserve
        """
        statements_changed = True

        while statements_changed:
            statements_changed = False

            # Iterate through each test case in the test suite
            for test_case_idx, test_case_chrom in enumerate(chromosome.test_case_chromosomes):
                test_case = test_case_chrom.test_case
                statements = list(test_case.statements)

                i = 0
                while i < len(statements):
                    stmt = statements[i]
                    if stmt.get_position() >= test_case.size():
                        break

                    # Create a clone of the entire test suite
                    test_suite_clone = chromosome.clone()
                    # Get the corresponding test case and statement in the clone
                    clone_test_case_chrom: tcc.TestCaseChromosome = (
                        test_suite_clone.get_test_case_chromosome(test_case_idx)
                    )
                    clone_test_case = clone_test_case_chrom.test_case
                    clone_stmt = clone_test_case.get_statement(stmt.get_position())

                    # Remove the statement from the clone
                    clone_test_case.remove_statement_with_forward_dependencies(clone_stmt)
                    test_suite_clone.set_test_case_chromosome(
                        test_case_idx, tcc.TestCaseChromosome(clone_test_case)
                    )

                    # Compute the coverage of the modified test suite
                    minimized_coverage = self._fitness_function.compute_coverage(test_suite_clone)

                    # If coverage is not affected, remove the statement from the original test case
                    if math.isclose(original_coverage, minimized_coverage):
                        removed = test_case.remove_statement_with_forward_dependencies(stmt)
                        self._removed_statements += len(removed)

                        # Update the statements list to reflect the changes in the test case
                        statements = list(test_case.statements)
                        # Update the test suite
                        chromosome.set_test_case_chromosome(
                            test_case_idx, tcc.TestCaseChromosome(test_case)
                        )
                        # Don't increment i since we've removed elements and the list has shifted
                        statements_changed = True
                    else:
                        i += 1

            # If no statements were changed in this iteration, we're done
            if not statements_changed:
                break


class EmptyTestCaseRemover(cv.ChromosomeVisitor):
    """Removes empty test cases from a test suite.

    If a test case is empty after minimization, it should be removed entirely.
    """

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
