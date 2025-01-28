#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides a factory to create test suite chromosomes."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pynguin.configuration as config
import pynguin.ga.chromosomefactory as cf
import pynguin.ga.testsuitechromosome as tsc

from pynguin.utils import randomness


if TYPE_CHECKING:
    import pynguin.ga.computations as ff

    from pynguin.utils.orderedset import OrderedSet


class TestSuiteChromosomeFactory(cf.ChromosomeFactory[tsc.TestSuiteChromosome]):
    """A factory that provides new test suite chromosomes of random length."""

    def __init__(
        self,
        test_case_chromosome_factory: cf.ChromosomeFactory,
        fitness_functions: OrderedSet[ff.TestSuiteFitnessFunction],
        coverage_functions: OrderedSet[ff.TestSuiteCoverageFunction],
    ):
        """Instantiates a new factory.

        Args:
            test_case_chromosome_factory: The internal test case chromosome factory,
                                          which provides the test case chromosomes that
                                          will be part of a newly generated test suite
                                          chromosome
            fitness_functions: The fitness functions that will be added to every
                               newly generated chromosome.
            coverage_functions: The coverage functions that will be added to every
                                newly generated chromosome.
        """
        self._test_case_chromosome_factory = test_case_chromosome_factory
        self._fitness_functions = fitness_functions
        self._coverage_functions = coverage_functions

    def get_chromosome(self) -> tsc.TestSuiteChromosome:  # noqa: D102
        chromosome = tsc.TestSuiteChromosome(self._test_case_chromosome_factory)
        num_tests = randomness.next_int(
            config.configuration.search_algorithm.min_initial_tests,
            config.configuration.search_algorithm.max_initial_tests + 1,
        )

        for _ in range(num_tests):
            chromosome.add_test_case_chromosome(self._test_case_chromosome_factory.get_chromosome())
        for fitness_function in self._fitness_functions:
            chromosome.add_fitness_function(fitness_function)
        for coverage_function in self._coverage_functions:
            chromosome.add_coverage_function(coverage_function)
        return chromosome
