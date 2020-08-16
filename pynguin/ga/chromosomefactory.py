#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Factory for chromosome used by the genetic algorithm."""
from abc import abstractmethod
from typing import Generic, TypeVar

import pynguin.configuration as config
import pynguin.ga.chromosome as chrom
import pynguin.ga.testcasefactory as tcf
import pynguin.testsuite.testsuitechromosome as tsc
from pynguin.utils import randomness

T = TypeVar("T", bound=chrom.Chromosome)  # pylint: disable=invalid-name


# pylint: disable=too-few-public-methods
class ChromosomeFactory(Generic[T]):
    """A factory that provides new chromosomes."""

    @abstractmethod
    def get_chromosome(self) -> T:
        """Create a new chromosome.

        Returns:
            A new chromosome  # noqa: DAR202
        """


class TestSuiteChromosomeFactory(ChromosomeFactory[tsc.TestSuiteChromosome]):
    """A factory that provides new test suite chromosomes of random length."""

    def __init__(self, test_case_factory: tcf.TestCaseFactory):
        """Instantiates a new factory

        Args:
            test_case_factory: The internal test case factory
        """
        self._test_case_factory = test_case_factory

    def get_chromosome(self) -> tsc.TestSuiteChromosome:
        chromosome = tsc.TestSuiteChromosome(self._test_case_factory)
        num_tests = randomness.next_int(
            config.INSTANCE.min_initial_tests, config.INSTANCE.max_initial_tests + 1
        )

        for _ in range(num_tests):
            chromosome.add_test(self._test_case_factory.get_test_case())

        return chromosome
