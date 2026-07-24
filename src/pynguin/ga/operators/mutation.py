#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Mutation operators for test-case and test-suite chromosomes."""

from __future__ import annotations

import abc
from typing import TYPE_CHECKING, Any

import pynguin.configuration as config
import pynguin.utils.generic.genericaccessibleobject as gao
from pynguin.utils import randomness

if TYPE_CHECKING:
    import pynguin.ga.testcasechromosome as tcc
    import pynguin.ga.testsuitechromosome as tsc
    import pynguin.testcase.testcase as tc


class MutationOperator(abc.ABC):
    """Abstract base class for mutation operators."""

    @abc.abstractmethod
    def mutate(self, chromosome: Any) -> None:
        """Mutate the given chromosome in-place.

        Args:
            chromosome: The chromosome to mutate
        """


class TestCaseMutation(MutationOperator):
    """Mutation operator for TestCaseChromosome."""

    def mutate(self, chromosome: tcc.TestCaseChromosome) -> None:
        """Apply mutation at test case level.

        Args:
            chromosome: The TestCaseChromosome to mutate
        """
        changed = False

        if (
            config.configuration.search_algorithm.chop_max_length
            and chromosome.size() >= config.configuration.search_algorithm.chromosome_length
        ):
            last_mutatable_position = chromosome.get_last_mutatable_statement()
            if last_mutatable_position is not None:
                # Remove all statements after the last mutatable position.
                chromosome.test_case.remove_statements_batch(
                    set(range(last_mutatable_position + 1, chromosome.test_case.size()))
                )
                changed = True

        # In case mutation removes all calls on the SUT.
        backup = chromosome.test_case.clone()

        if (
            randomness.next_float() <= config.configuration.search_algorithm.test_delete_probability
            and chromosome._mutation_delete()  # noqa: SLF001
        ):
            changed = True

        if (
            randomness.next_float() <= config.configuration.search_algorithm.test_change_probability
            and chromosome._mutation_change()  # noqa: SLF001
        ):
            changed = True

        if (
            randomness.next_float() <= config.configuration.search_algorithm.test_insert_probability
            and chromosome._mutation_insert()  # noqa: SLF001
        ):
            changed = True

        assert chromosome._test_factory, "Required for mutation"  # noqa: SLF001
        if not chromosome._test_factory.has_call_on_sut(chromosome.test_case):  # noqa: SLF001
            chromosome.test_case = backup
            chromosome._mutation_insert()  # noqa: SLF001

        if changed:
            chromosome.changed = True
            chromosome._num_mutations += 1  # noqa: SLF001

    def _mutation_delete(self, chromosome: tcc.TestCaseChromosome) -> bool:
        last_mutatable_statement = chromosome.get_last_mutatable_statement()
        if last_mutatable_statement is None:
            return False

        changed = False
        p_per_statement = 1.0 / (last_mutatable_statement + 1)
        for idx in reversed(range(last_mutatable_statement + 1)):
            if idx >= chromosome.size():
                continue
            if randomness.next_float() <= p_per_statement:
                changed |= chromosome._delete_statement(idx)  # noqa: SLF001
        return changed

    def _delete_statement(self, chromosome: tcc.TestCaseChromosome, idx: int) -> bool:
        assert chromosome._test_factory, "Mutation requires a test factory."  # noqa: SLF001
        return chromosome._test_factory.delete_statement_gracefully(  # noqa: SLF001
            chromosome.test_case, idx
        )

    def _mutation_change(self, chromosome: tcc.TestCaseChromosome) -> bool:
        last_mutatable_statement = chromosome.get_last_mutatable_statement()
        if last_mutatable_statement is None:
            return False

        changed = False
        p_per_statement = 1.0 / (last_mutatable_statement + 1.0)
        position = 0
        while position <= last_mutatable_statement and position < chromosome.size():
            if randomness.next_float() < p_per_statement:
                statement = chromosome.test_case.get_statement(position)
                if statement.bound_variable is not None and chromosome._mutate_statement(  # noqa: SLF001
                    position, statement
                ):
                    changed = True
            position += 1

        return changed

    def _mutate_statement(
        self,
        chromosome: tcc.TestCaseChromosome,
        position: int,
        statement: tc.Statement,
    ) -> bool:
        """Apply a single change mutation to the statement at *position*.

        Args:
            chromosome: The chromosome being mutated.
            position: The index of the statement to mutate.
            statement: The statement at *position*.

        Returns:
            Whether the statement was changed.
        """
        assert chromosome._test_factory, "Mutation requires a test factory."  # noqa: SLF001
        if (
            randomness.next_float()
            < config.configuration.search_algorithm.change_statement_type_probability
            and chromosome._test_factory.change_statement_type(  # noqa: SLF001
                chromosome.test_case, position
            )
        ):
            # Replace the statement with one of a different type, keeping its
            # bound variable (Evosuite change_statement_type). On failure, fall
            # through to the regular value/call mutation below.
            return True
        if statement.accessible is None:
            # Primitive statement: regenerate the literal value.
            return chromosome._test_factory.mutate_value(  # noqa: SLF001
                chromosome.test_case, position
            )
        if isinstance(statement.accessible, gao.GenericField):
            # Field statement: swap the accessed field, else re-pick the receiver.
            return chromosome._test_factory.change_random_field_call(  # noqa: SLF001
                chromosome.test_case, position
            ) or chromosome._test_factory.mutate_call(  # noqa: SLF001
                chromosome.test_case, position
            )
        # Call statement: first try to regenerate argument values (mirrors the
        # original statement.mutate() path), then fall back to replacing the
        # call with a different one.
        return chromosome._test_factory.mutate_call(  # noqa: SLF001
            chromosome.test_case, position
        ) or chromosome._test_factory.change_random_call(  # noqa: SLF001
            chromosome.test_case, position
        )

    def _mutation_insert(self, chromosome: tcc.TestCaseChromosome) -> bool:
        """Insertion mutation operation.

        With exponentially decreasing probability, insert statements at a random
        position.

        Args:
            chromosome: The chromosome being mutated.

        Returns:
            Whether the test case was changed
        """
        changed = False
        alpha = config.configuration.search_algorithm.statement_insertion_probability
        exponent = 1
        while (
            randomness.next_float() <= pow(alpha, exponent)
            and chromosome.size() < config.configuration.search_algorithm.chromosome_length
        ):
            assert chromosome._test_factory, "Mutation requires a test factory."  # noqa: SLF001
            max_position = chromosome.get_last_mutatable_statement()
            if max_position is None:
                # No mutatable statement found, so start at the first position.
                max_position = 0
            else:
                # Also include the position after the last mutatable statement.
                max_position += 1

            position = chromosome._test_factory.insert_random_statement(  # noqa: SLF001
                chromosome.test_case, max_position
            )
            exponent += 1
            if 0 <= position < chromosome.size():
                changed = True
        return changed


class TestSuiteMutation(MutationOperator):
    """Mutation operator for TestSuiteChromosome."""

    def mutate(self, chromosome: tsc.TestSuiteChromosome) -> None:
        """Apply mutation at test suite level.

        Args:
            chromosome: The TestSuiteChromosome to mutate
        """
        assert chromosome.test_case_chromosome_factory is not None, (
            "Mutation is not possibly without test case chromosome factory"
        )

        changed = False

        # Mutate existing test cases.
        for test in chromosome.test_case_chromosomes:
            if randomness.next_float() < 1.0 / chromosome.size():
                test.mutate()
                if test.changed:
                    changed = True

        # Randomly add new test cases.
        alpha = config.configuration.search_algorithm.test_insertion_probability
        exponent = 1
        while (
            randomness.next_float() <= pow(alpha, exponent)
            and chromosome.size() < config.configuration.test_creation.max_size
        ):
            chromosome.add_test_case_chromosome(
                chromosome.test_case_chromosome_factory.get_chromosome()
            )
            exponent += 1
            changed = True

        # Remove any tests that have no more statements left.
        chromosome.test_case_chromosomes = [
            t for t in chromosome.test_case_chromosomes if t.size() > 0
        ]

        if changed:
            chromosome.changed = True


# Singletons for chromosome delegation
_TEST_CASE_MUTATION = TestCaseMutation()
_TEST_SUITE_MUTATION = TestSuiteMutation()
