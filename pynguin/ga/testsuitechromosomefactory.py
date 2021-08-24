#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides a factory to create test suite chromosomes."""
from typing import List

import pynguin.configuration as config
import pynguin.ga.chromosomefactory as cf
import pynguin.ga.fitnessfunction as ff
import pynguin.ga.testcasechromosomefactory as tccf
import pynguin.ga.testsuitechromosome as tsc
from pynguin.utils import randomness


class TestSuiteChromosomeFactory(
    cf.ChromosomeFactory[tsc.TestSuiteChromosome]
):  # pylint:disable=too-few-public-methods.
    """A factory that provides new test suite chromosomes of random length."""

    def __init__(
        self,
        test_case_chromosome_factory: tccf.TestCaseChromosomeFactory,
        fitness_functions: List[ff.FitnessFunction],
    ):
        """Instantiates a new factory

        Args:
            test_case_chromosome_factory: The internal test case chromosome factory,
                                          which provides the test case chromosomes that
                                          will be part of a newly generated test suite
                                          chromosome
            fitness_functions: The fitness functions that will be added to every
                               newly generated chromosome.
        """
        self._test_case_chromosome_factory = test_case_chromosome_factory
        self._fitness_functions = fitness_functions

    def get_chromosome(self) -> tsc.TestSuiteChromosome:
        chromosome = tsc.TestSuiteChromosome(self._test_case_chromosome_factory)
        num_tests = randomness.next_int(
            config.configuration.search_algorithm.min_initial_tests,
            config.configuration.search_algorithm.max_initial_tests + 1,
        )

        for _ in range(num_tests):
            chromosome.add_test_case_chromosome(
                self._test_case_chromosome_factory.get_chromosome()
            )
        for func in self._fitness_functions:
            chromosome.add_fitness_function(func)
        return chromosome
