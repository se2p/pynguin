#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides a chromosome for a single test case."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pynguin.configuration as config
import pynguin.ga.chromosome as chrom
import pynguin.testcase.statement as stmt

from pynguin.utils import randomness


if TYPE_CHECKING:
    import pynguin.ga.chromosomevisitor as cv
    import pynguin.testcase.testcase as tc
    import pynguin.testcase.testfactory as tf

    from pynguin.testcase.execution import ExecutionResult


class TestCaseChromosome(chrom.Chromosome):
    """A chromosome that encodes a single test case."""

    def __init__(
        self,
        test_case: tc.TestCase | None = None,
        test_factory: tf.TestFactory | None = None,
        orig: TestCaseChromosome | None = None,
    ) -> None:
        """Initializes a new test-case chromosome.

        Must supply either a TestCaseChromosome to copy from or the remaining arguments.

        Args:
            test_case: The test case that is encoded by this chromosome.
            test_factory: Test factory used to manipulate the underlying test case.
            orig: Original, if we clone an existing chromosome.
        """
        super().__init__(orig=orig)
        if orig is None:
            assert test_case is not None, "Cannot create test case chromosome without test case"
            self._test_case: tc.TestCase = test_case
            self._test_factory: tf.TestFactory | None = test_factory
            self.changed = True
            self._last_execution_result: ExecutionResult | None = None
            self._num_mutations = 0
        else:
            self._test_case = orig._test_case.clone()  # noqa: SLF001
            self._test_factory = orig._test_factory  # noqa: SLF001
            self.changed = orig.changed
            self._last_execution_result = orig._last_execution_result  # noqa: SLF001
            self._num_mutations = orig._num_mutations  # noqa: SLF001

    @property
    def test_case(self) -> tc.TestCase:
        """The test case that is wrapped by this chromosome.

        Returns:
            the wrapped test case.
        """
        return self._test_case

    def num_mutations(self) -> int:
        """The number of mutations.

        Returns:
            the number of mutations.
        """
        # TODO(fk) what to do with this when crossover is used?
        return self._num_mutations

    def size(self) -> int:  # noqa: D102
        return self._test_case.size()

    def length(self) -> int:  # noqa: D102
        return self.size()

    def cross_over(  # noqa: D102
        self, other: chrom.Chromosome, position1: int, position2: int
    ) -> None:
        assert isinstance(other, TestCaseChromosome), "Cannot perform crossover with " + str(
            type(other)
        )
        assert self._test_factory is not None, "Crossover requires a test factory."

        offspring_test_case = self.test_case.clone(position1)

        for j in range(position2, other.test_case.size()):
            self._test_factory.append_statement(
                offspring_test_case, other.test_case.get_statement(j)
            )

        if offspring_test_case.size() < config.configuration.search_algorithm.chromosome_length:
            self._test_case = offspring_test_case
            self.changed = True

    def mutate(self) -> None:  # noqa: D102
        changed = False

        if (
            config.configuration.search_algorithm.chop_max_length
            and self.size() >= config.configuration.search_algorithm.chromosome_length
        ):
            last_mutatable_position = self.get_last_mutatable_statement()
            if last_mutatable_position is not None:
                self._test_case.chop(last_mutatable_position)
                changed = True

        # In case mutation removes all calls on the SUT.
        backup = self.test_case.clone()

        if (
            randomness.next_float() <= config.configuration.search_algorithm.test_delete_probability
            and self._mutation_delete()
        ):
            changed = True

        if (
            randomness.next_float() <= config.configuration.search_algorithm.test_change_probability
            and self._mutation_change()
        ):
            changed = True

        if (
            randomness.next_float() <= config.configuration.search_algorithm.test_insert_probability
            and self._mutation_insert()
        ):
            changed = True

        assert self._test_factory, "Required for mutation"
        if not self._test_factory.has_call_on_sut(self._test_case):
            self._test_case = backup
            self._mutation_insert()

        if changed:
            self.changed = True
            self._num_mutations += 1

    def _mutation_delete(self) -> bool:
        last_mutatable_statement = self.get_last_mutatable_statement()
        if last_mutatable_statement is None:
            return False

        changed = False
        p_per_statement = 1.0 / (last_mutatable_statement + 1)
        for idx in reversed(range(last_mutatable_statement + 1)):
            if idx >= self.size():
                continue
            if randomness.next_float() <= p_per_statement:
                changed |= self._delete_statement(idx)
        return changed

    def _delete_statement(self, idx: int) -> bool:
        assert self._test_factory, "Mutation requires a test factory."
        return self._test_factory.delete_statement_gracefully(self._test_case, idx)

    def _mutation_change(self) -> bool:
        last_mutatable_statement = self.get_last_mutatable_statement()
        if last_mutatable_statement is None:
            return False

        changed = False
        p_per_statement = 1.0 / (last_mutatable_statement + 1.0)
        position = 0
        while position <= last_mutatable_statement:
            if randomness.next_float() < p_per_statement:
                statement = self._test_case.get_statement(position)
                if not isinstance(statement, stmt.VariableCreatingStatement):
                    continue
                old_distance = statement.ret_val.distance
                ret_val = statement.ret_val
                if statement.mutate():
                    changed = True
                else:
                    assert self._test_factory, "Mutation requires a test factory."
                    if self._test_factory.change_random_call(
                        self._test_case,
                        statement,
                    ):
                        changed = True
                statement.ret_val.distance = old_distance
                position = ret_val.get_statement_position()
            position += 1

        return changed

    def _mutation_insert(self) -> bool:
        """Insertion mutation operation.

        With exponentially decreasing probability, insert statements at a random
        position.

        Returns:
            Whether the test case was changed
        """
        changed = False
        alpha = config.configuration.search_algorithm.statement_insertion_probability
        exponent = 1
        while (
            randomness.next_float() <= pow(alpha, exponent)
            and self.size() < config.configuration.search_algorithm.chromosome_length
        ):
            assert self._test_factory, "Mutation requires a test factory."
            max_position = self.get_last_mutatable_statement()
            if max_position is None:
                # No mutatable statement found, so start at the first position.
                max_position = 0
            else:
                # Also include the position after the last mutatable statement.
                max_position += 1

            position = self._test_factory.insert_random_statement(self._test_case, max_position)
            exponent += 1
            if 0 <= position < self.size():
                changed = True
        return changed

    def get_last_mutatable_statement(self) -> int | None:
        """Provides the index of the last mutatable statement of the wrapped test case.

        If there was an exception during the last execution, this includes all statement
        up to the one that caused the exception (included).

        Returns:
            The index of the last mutatable statement, if any.
        """
        # We are empty, so there can't be a last mutatable statement.
        if self.size() == 0:
            return None

        result = self.get_last_execution_result()
        if result is not None and result.has_test_exceptions():
            position = result.get_first_position_of_thrown_exception()
            assert position is not None
            # The position might not be valid anymore.
            if position < self.size():
                return position
        # No exception, so the entire test case can be mutated.
        return self.size() - 1

    def get_last_execution_result(self) -> ExecutionResult | None:
        """Get the last execution result.

        Returns:
            The last execution result if any  # noqa: DAR202
        """
        return self._last_execution_result

    def set_last_execution_result(self, result: ExecutionResult) -> None:
        """Set the last execution result.

        Args:
            result: The last execution result
        """
        self._last_execution_result = result

    def remove_last_execution_result(self) -> None:
        """Removes the last execution result."""
        self._last_execution_result = None

    def is_failing(self) -> bool:
        """Returns whether or not the encapsulated test case is a failing test.

        A failing test is a test that raises an exception.
        TODO(sl) what about test cases raising exceptions on purpose?

        Returns:
            Whether or not the encapsulated test case is a failing test.  # noqa: DAR202
        """
        if not self._last_execution_result:
            return False
        return self._last_execution_result.has_test_exceptions()

    def accept(self, visitor: cv.ChromosomeVisitor) -> None:  # noqa: D102
        visitor.visit_test_case_chromosome(self)

    def clone(self) -> TestCaseChromosome:  # noqa: D102
        return TestCaseChromosome(orig=self)

    def __eq__(self, other):
        if self is other:
            return True
        if not isinstance(other, TestCaseChromosome):
            return False
        # This condition is playing with fire, but it is required to not lose coverage
        # information on flaky tests. For more information on this see #169.
        # Be careful when comparing TestCaseChromosomes!
        if (left := self._last_execution_result) is not None and (  # noqa: SIM102
            right := other._last_execution_result
        ) is not None:
            if left.execution_trace != right.execution_trace:
                return False
        return self._test_case == other._test_case

    def __hash__(self):
        return hash(self._test_case)
