#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides a random test generator, that creates random test suites."""
import logging

import pynguin.ga.testsuitechromosome as tsc
import pynguin.utils.statistics.statistics as stat
from pynguin.generation.algorithms.testgenerationstrategy import TestGenerationStrategy
from pynguin.utils.statistics.runtimevariable import RuntimeVariable


# pylint: disable=too-few-public-methods
class RandomSearchStrategy(TestGenerationStrategy):
    """Create random test suites."""

    _logger = logging.getLogger(__name__)

    def generate_tests(
        self,
    ) -> tsc.TestSuiteChromosome:
        solution = self._get_random_solution()
        stat.current_individual(solution)
        generation = 0
        while (
            not self._stopping_condition.is_fulfilled()
            and solution.get_fitness() != 0.0
        ):
            candidate = self._get_random_solution()
            if candidate.get_fitness() < solution.get_fitness():
                solution = candidate
                self._logger.info(
                    "Generation: %5i. Best fitness: %5f, Best coverage %5f",
                    generation,
                    solution.get_fitness(),
                    solution.get_coverage(),
                )
            stat.current_individual(solution)
            generation += 1
        stat.track_output_variable(RuntimeVariable.AlgorithmIterations, generation)
        return solution

    def _get_random_solution(self) -> tsc.TestSuiteChromosome:
        """Small helper to create new solution and add fitness functions."""
        solution = self._chromosome_factory.get_chromosome()
        for fitness_function in self._fitness_functions:
            solution.add_fitness_function(fitness_function)

        return solution
