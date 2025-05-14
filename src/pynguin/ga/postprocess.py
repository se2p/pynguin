#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides chromosome visitors to perform post-processing."""

from __future__ import annotations

import logging

from abc import ABC
from typing import TYPE_CHECKING

import pynguin.ga.chromosomevisitor as cv
import pynguin.ga.testcasechromosome as tcc
import pynguin.ga.testsuitechromosome as tsc
import pynguin.testcase.testcasevisitor as tcv

from pynguin.assertion.assertion import Assertion
from pynguin.assertion.assertion import ExceptionAssertion
from pynguin.testcase.statement import StatementVisitor
from pynguin.utils.orderedset import OrderedSet


if TYPE_CHECKING:
    import pynguin.ga.computations as ff


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

    _logger = logging.getLogger(__name__)

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

        self._logger.debug(
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
            if (last_exec := chromosome.get_last_execution_result()) is not None:
                # We don't want to re-execute the test cases here, so we also remove
                # information about the deleted statements from the execution result.
                # TODO(fk) we could also re-execute, but with flakiness this could
                #  cause inconsistent results
                last_exec.delete_statement_data(visitor.deleted_statement_indexes)


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
    2. Remove the statement from the clone and all forward dependent statements
    3. Execute the clone and calculate its fitness
    4. If fitness remains the same or improves, remove the statement from the original test case
    """

    _logger = logging.getLogger(__name__)

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

    def visit_default_test_case(self, test_case) -> None:  # noqa: D102
        self._deleted_statement_indexes.clear()
        original_size = test_case.size()

        # We need to iterate over a copy of the statements because we'll be modifying the test case
        statements = list(test_case.statements)

        # For each statement, try to remove it and see if fitness is preserved
        for stmt in statements:
            if stmt.get_position() >= test_case.size():
                continue
            ret_val = stmt.ret_val

            test_clone = self._create_clone_without_stmt(stmt, test_case)
            coverage_reduced = self._compare_coverage(test_case, test_clone)
            if not coverage_reduced:
                forward_dependencies = []
                if ret_val is not None:
                    forward_dependencies = list(test_case.get_forward_dependencies(ret_val))
                # Remove the statement and its forward dependencies
                # We need to remove them one by one, updating positions after each removal
                # Start with the statement itself
                self._deleted_statement_indexes.add(stmt.get_position())
                test_case.remove(stmt.get_position())
                self._removed_statements += 1
                for dep in forward_dependencies:
                    current_pos = dep.get_statement_position()
                    test_case.remove(current_pos)
                    self._deleted_statement_indexes.add(current_pos)
                    self._removed_statements += 1

        self._logger.debug(
            "Removed %s statement(s) from test case using iterative minimization",
            original_size - test_case.size(),
        )

    def _create_clone_without_stmt(self, stmt, test_case):
        # Create a clone of the test case for testing
        test_clone = test_case.clone()
        clone_stmt = test_clone.get_statement(stmt.get_position())
        clone_ret_val = clone_stmt.ret_val
        # Get forward dependencies in the clone
        forward_dependencies = []
        if clone_ret_val is not None:
            forward_dependencies = list(test_clone.get_forward_dependencies(clone_ret_val))
        # Remove the statement and its forward dependencies from the clone
        # Remove in reverse order to avoid index issues
        positions_to_remove = sorted(
            [dep.get_statement_position() for dep in forward_dependencies]
            + [clone_stmt.get_position()],
            reverse=True,
        )
        for pos in positions_to_remove:
            test_clone.remove(pos)
        return test_clone

    def _compare_coverage(self, test_case, test_clone):
        # Calculate fitness with the modified clone
        test_case_chromosome = tcc.TestCaseChromosome(test_case=test_clone)
        # Get all test case chromosomes from the original test suite
        original_test_case = tcc.TestCaseChromosome(test_case=test_case)
        original_test_suite = tsc.TestSuiteChromosome()
        original_test_suite.add_test_case_chromosome(original_test_case)
        original_coverage = self._fitness_function.compute_coverage(original_test_suite)
        # Create a test suite with the modified clone and all other test case chromosomes
        test_suite_chromosome = tsc.TestSuiteChromosome()
        test_suite_chromosome.add_test_case_chromosome(test_case_chromosome)
        modified_coverage = self._fitness_function.compute_coverage(test_suite_chromosome)
        return modified_coverage < original_coverage


class UnusedStatementsTestCaseVisitor(ModificationAwareTestCaseVisitor):
    """Removes unused primitive and collection statements."""

    _logger = logging.getLogger(__name__)

    def visit_default_test_case(self, test_case) -> None:  # noqa: D102
        self._deleted_statement_indexes.clear()
        primitive_remover = UnusedPrimitiveOrCollectionStatementVisitor()
        size_before = test_case.size()
        # Iterate over copy, to be able to modify original.
        for stmt in reversed(list(test_case.statements)):
            stmt.accept(primitive_remover)
        self._logger.debug(
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

    def visit_set_statement(self, stmt) -> None:  # noqa: D102
        self._handle_collection_or_primitive(stmt)

    def visit_tuple_statement(self, stmt) -> None:  # noqa: D102
        self._handle_collection_or_primitive(stmt)

    def visit_dict_statement(self, stmt) -> None:  # noqa: D102
        self._handle_collection_or_primitive(stmt)

    def visit_ast_assign_statement(self, stmt) -> None:  # noqa: D102
        self._handle_remaining(stmt)
