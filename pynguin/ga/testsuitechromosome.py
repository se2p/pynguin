#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides a test suite chromosome."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pynguin.configuration as config
import pynguin.ga.chromosome as chrom
from pynguin.utils import randomness

if TYPE_CHECKING:
    import pynguin.ga.chromosomefactory as cf
    import pynguin.ga.chromosomevisitor as cv
    import pynguin.ga.testcasechromosome as tcc


class TestSuiteChromosome(chrom.Chromosome):
    """A chromosome that encodes a test suite."""

    def __init__(
        self,
        test_case_chromosome_factory: None
        | (cf.ChromosomeFactory[tcc.TestCaseChromosome]) = None,
        orig: TestSuiteChromosome | None = None,
    ):
        """
        Create new test suite chromosome.

        Args:
            test_case_chromosome_factory: Factory that produces new test case
                chromosomes. Required, if you want to mutated this
                chromosome.
            orig: Original, if we clone an existing chromosome.
        """
        super().__init__(orig=orig)

        if orig is None:
            self._test_case_chromosome_factory: None | (
                cf.ChromosomeFactory[tcc.TestCaseChromosome]
            ) = test_case_chromosome_factory
            self._test_case_chromosomes: list[tcc.TestCaseChromosome] = []
        else:
            self._test_case_chromosomes = [
                chromosome.clone() for chromosome in orig._test_case_chromosomes
            ]
            self._test_case_chromosome_factory = orig._test_case_chromosome_factory

    def add_test_case_chromosome(self, test: tcc.TestCaseChromosome) -> None:
        """Adds a test case chromosome to the test suite.

        Args:
            test: the test case to be added
        """
        self._test_case_chromosomes.append(test)
        self.set_changed(True)

    def delete_test_case_chromosome(self, test: tcc.TestCaseChromosome) -> None:
        """Delete a test case from the test suite.

        Args:
            test: the test case chromosome to delete
        """
        try:
            self._test_case_chromosomes.remove(test)
            self.set_changed(True)
        except ValueError:
            pass

    def add_test_case_chromosomes(self, tests: list[tcc.TestCaseChromosome]) -> None:
        """Adds a list of test cases to the test suite.

        Args:
            tests: A list of test case chromosomes to add
        """
        self._test_case_chromosomes.extend(tests)
        if tests:
            self.set_changed(True)

    def clone(self) -> TestSuiteChromosome:
        """Clones the chromosome.

        Returns:
            A clone of the chromosome  # noqa: DAR202
        """
        return TestSuiteChromosome(orig=self)

    def get_test_case_chromosome(self, index: int) -> tcc.TestCaseChromosome:
        """Provides the test case chromosome at a certain index.

        Args:
            index: the index to select

        Returns:
            The test case chromosome at the given index
        """
        return self._test_case_chromosomes[index]

    @property
    def test_case_chromosomes(self) -> list[tcc.TestCaseChromosome]:
        """Provides all test chromosomes.

        Returns:
            The list of all test cases
        """
        return self._test_case_chromosomes

    def set_test_case_chromosome(
        self, index: int, test: tcc.TestCaseChromosome
    ) -> None:
        """Sets a test chromosome at a certain index.

        Args:
            index: the index to set the chromosome
            test: the test case to set
        """
        self._test_case_chromosomes[index] = test
        self.set_changed(True)

    def size(self) -> int:
        """Provides the size of the chromosome, i.e., its number of test cases.

        Returns:
            The size of the chromosome
        """
        return len(self._test_case_chromosomes)

    def length(self) -> int:
        return sum(test.length() for test in self._test_case_chromosomes)

    def cross_over(
        self, other: chrom.Chromosome, position1: int, position2: int
    ) -> None:
        """Performs the crossover with another chromosome.

        Keep tests up to position1. Append copies of tests from other from position2
        onwards.

        Args:
            other: the other chromosome
            position1: the position in the first chromosome
            position2: the position in the second chromosome
        """
        assert isinstance(
            other, TestSuiteChromosome
        ), "Cannot perform crossover with " + str(type(other))

        self._test_case_chromosomes = self._test_case_chromosomes[:position1] + [
            test.clone() for test in other._test_case_chromosomes[position2:]
        ]
        self.set_changed(True)

    def mutate(self) -> None:
        """Apply mutation at test suite level."""
        assert (
            self._test_case_chromosome_factory is not None
        ), "Mutation is not possibly without test case chromosome factory"

        changed = False

        # Mutate existing test cases.
        for test in self._test_case_chromosomes:
            if randomness.next_float() < 1.0 / self.size():
                test.mutate()
                if test.has_changed():
                    changed = True

        # Randomly add new test cases.
        alpha = config.configuration.search_algorithm.test_insertion_probability
        exponent = 1
        while (
            randomness.next_float() <= pow(alpha, exponent)
            and self.size() < config.configuration.test_creation.max_size
        ):
            self.add_test_case_chromosome(
                self._test_case_chromosome_factory.get_chromosome()
            )
            exponent += 1
            changed = True

        # Remove any tests that have no more statements left.
        self._test_case_chromosomes = [
            t for t in self._test_case_chromosomes if t.size() > 0
        ]

        if changed:
            self.set_changed(True)

    def accept(self, visitor: cv.ChromosomeVisitor) -> None:
        visitor.visit_test_suite_chromosome(self)

    def __eq__(self, other: Any) -> bool:
        if self is other:
            return True
        if not isinstance(other, TestSuiteChromosome):
            return False
        if self.size() != other.size():
            return False
        for test, other_test in zip(
            self._test_case_chromosomes, other._test_case_chromosomes
        ):
            if test != other_test:
                return False
        return True

    def __hash__(self) -> int:
        return 31 + sum(17 * hash(t) for t in self._test_case_chromosomes)
