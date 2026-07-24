#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides a test suite chromosome."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pynguin.ga.chromosome as chrom

if TYPE_CHECKING:
    import pynguin.ga.chromosomefactory as cf
    import pynguin.ga.chromosomevisitor as cv
    import pynguin.ga.testcasechromosome as tcc


class TestSuiteChromosome(chrom.Chromosome):
    """A chromosome that encodes a test suite."""

    def __init__(
        self,
        test_case_chromosome_factory: (cf.ChromosomeFactory[tcc.TestCaseChromosome] | None) = None,
        orig: TestSuiteChromosome | None = None,
    ):
        """Create new test suite chromosome.

        Args:
            test_case_chromosome_factory: Factory that produces new test case
                chromosomes. Required, if you want to mutate this
                chromosome.
            orig: Original, if we clone an existing chromosome.
        """
        super().__init__(orig=orig)

        if orig is None:
            self.test_case_chromosome_factory: (
                None | (cf.ChromosomeFactory[tcc.TestCaseChromosome])  # noqa: RUF036
            ) = test_case_chromosome_factory
            self.test_case_chromosomes: list[tcc.TestCaseChromosome] = []
        else:
            self.test_case_chromosomes = [
                chromosome.clone() for chromosome in orig.test_case_chromosomes
            ]
            self.test_case_chromosome_factory = orig.test_case_chromosome_factory

    def add_test_case_chromosome(self, test: tcc.TestCaseChromosome) -> None:
        """Adds a test case chromosome to the test suite.

        Args:
            test: the test case to be added
        """
        self.test_case_chromosomes.append(test)
        self.changed = True

    def delete_test_case_chromosome(self, test: tcc.TestCaseChromosome) -> None:
        """Delete a test case from the test suite.

        Args:
            test: the test case chromosome to delete
        """
        try:
            self.test_case_chromosomes.remove(test)
            self.changed = True
        except ValueError:
            pass

    def add_test_case_chromosomes(self, tests: list[tcc.TestCaseChromosome]) -> None:
        """Adds a list of test cases to the test suite.

        Args:
            tests: A list of test case chromosomes to add
        """
        self.test_case_chromosomes.extend(tests)
        if tests:
            self.changed = True

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
        return self.test_case_chromosomes[index]

    def set_test_case_chromosome(self, index: int, test: tcc.TestCaseChromosome) -> None:
        """Sets a test chromosome at a certain index.

        Args:
            index: the index to set the chromosome
            test: the test case to set
        """
        self.test_case_chromosomes[index] = test
        self.changed = True

    def size(self) -> int:
        """Provides the size of the chromosome, i.e., its number of test cases.

        Returns:
            The size of the chromosome
        """
        return len(self.test_case_chromosomes)

    def length(self) -> int:  # noqa: D102
        return sum(test.length() for test in self.test_case_chromosomes)

    def cross_over(self, other: chrom.Chromosome, position1: int, position2: int) -> None:
        """Performs the crossover with another chromosome.

        Keep tests up to position1. Append copies of tests from other from position2
        onwards.

        Args:
            other: the other chromosome
            position1: the position in the first chromosome
            position2: the position in the second chromosome
        """
        assert isinstance(other, TestSuiteChromosome), "Cannot perform crossover with " + str(
            type(other)
        )
        from pynguin.ga.operators.crossover import splice_test_suite_chromosomes  # noqa: PLC0415

        splice_test_suite_chromosomes(self, other, position1, position2)

    def mutate(self) -> None:  # noqa: D102
        from pynguin.ga.operators.mutation import _TEST_SUITE_MUTATION  # noqa: PLC0415

        _TEST_SUITE_MUTATION.mutate(self)

    def accept(self, visitor: cv.ChromosomeVisitor) -> None:  # noqa: D102
        visitor.visit_test_suite_chromosome(self)

    def __eq__(self, other: object) -> bool:
        if self is other:
            return True
        if not isinstance(other, TestSuiteChromosome):
            return False
        if self.size() != other.size():
            return False
        for test, other_test in zip(
            self.test_case_chromosomes, other.test_case_chromosomes, strict=True
        ):
            if test != other_test:
                return False
        return True

    def __hash__(self) -> int:
        return 31 + sum(17 * hash(t) for t in self.test_case_chromosomes)
