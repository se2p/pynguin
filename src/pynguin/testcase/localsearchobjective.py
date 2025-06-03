#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
"""Provides the local search strategies."""
from __future__ import annotations

import logging

from pynguin.ga.chromosome import Chromosome
from pynguin.ga.testcasechromosome import TestCaseChromosome
from pynguin.ga.testsuitechromosome import TestSuiteChromosome


class LocalSearchObjective:
    """A local search objective which is used to monitor the success of the current local search on a chromosome"""

    _logger = logging.getLogger(__name__)

    def __init__(self, test_suite: TestSuiteChromosome, position:int) -> None:
        """Create a new local search objective object.
        Args:

            position: The position of the specific test case which will be modified.
            test_suite: The whole testsuite.
            """
        self._old_fitness: float = 0.0
        self._test_suite = test_suite
        self._position = position
        self._fitness_functions = test_suite.get_fitness_functions()
        self._latest_coverage_map = dict()
        self._latest_fitness_map = dict()
        self._updateLatestFitnessMap()
        self._updateLatestCoverageMap()

        self._is_maximization = self._fitness_functions[0].is_maximisation_function() if self._fitness_functions else False

    def _updateLatestCoverageMap(self) -> None:
        self._oldFitness = 0.0
        for fitness_function in self._fitness_functions:
            fitness = self._test_suite.get_fitness_for(fitness_function)
            self._oldFitness += fitness
            self._latest_fitness_map[fitness_function] = fitness

    def _updateLatestFitnessMap(self) -> None:
        for coverage_function in self._test_suite.get_coverage_functions():
            self._latest_coverage_map[coverage_function] = self._test_suite.get_coverage_for(coverage_function)

    def has_changed(self, test_case_chromosome:TestCaseChromosome) -> int:
        """ Gives back, if the fitness of the testsuite has changed. It overrides the specific testcase with the provided chromosome.

        Args:
            test_case_chromosome: The chromosome which will override the original chromosome.

        Returns:
            Gives back 1 if the fitness has increased, -1 if the fitness has decreased and 0 if the fitness has not changed at all.
        """
        test_case_chromosome.changed = True
        self._old_fitness = self._test_suite.get_fitness()
        self._test_suite.set_test_case_chromosome(self._position, test_case_chromosome)
        for fitness_function in self._fitness_functions:
            fitness_function.compute_fitness(self._test_suite)
        new_fitness = self._test_suite.get_fitness()

        if new_fitness > self._old_fitness if self._is_maximization else new_fitness < self._old_fitness:
            self._logger.debug("Local search has increased the fitness of %f to %f", self._old_fitness, new_fitness)
            self._updateLatestCoverageMap()
            self._updateLatestFitnessMap()
            return 1
        elif new_fitness < self._old_fitness if self._is_maximization else new_fitness > self._old_fitness:
            self._logger.debug("Local search has decreased the fitness of %f to %f", self._old_fitness, new_fitness)
            self._test_suite.set_coverage_values(self._latest_coverage_map)
            self._test_suite.set_fitness_values(self._latest_fitness_map)
            return -1
        else:
            self._logger.debug("Local search hasn't changed the fitness of %f", self._old_fitness)
            return 0

    def has_improved(self, test_case_chromosome:TestCaseChromosome) -> bool:
        """Gives back if changing the old test case chromosome to the given one improves the fitness of the test suite.

        Args:
            test_case_chromosome: The chromosome which will override the original chromosome.

        Returns:
            Gives back true, if the test suite has improved.
        """
        return self.has_changed(test_case_chromosome) > 0
