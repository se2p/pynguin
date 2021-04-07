#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides a random test generator, that creates random test suites."""
import logging
from typing import cast

import pynguin.ga.chromosome as chrom
import pynguin.ga.fitnessfunction as ff
import pynguin.ga.testcasechromosome as tcc
import pynguin.ga.testsuitechromosome as tsc
import pynguin.utils.statistics.statistics as stat
from pynguin.generation.algorithms.archive import Archive
from pynguin.generation.algorithms.testgenerationstrategy import TestGenerationStrategy
from pynguin.generation.algorithms.wraptestsuitemixin import WrapTestSuiteMixin
from pynguin.utils.statistics.runtimevariable import RuntimeVariable


# pylint: disable=too-few-public-methods
class RandomTestSuiteSearchStrategy(TestGenerationStrategy):
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


class RandomTestCaseSearchStrategy(TestGenerationStrategy, WrapTestSuiteMixin):
    """Creates random test suites based on test-case chromosomes."""

    _logger = logging.getLogger(__name__)

    def __init__(self) -> None:
        super().__init__()
        self._archive: Archive[ff.FitnessFunction, tcc.TestCaseChromosome]
        self._current_iteration = 0

    def generate_tests(self) -> chrom.Chromosome:
        self._archive = Archive(set(self._fitness_functions))
        self._current_iteration = 0
        solution = self._get_random_solution()
        self._archive.update([solution])
        test_suite = self._notify_iteration()

        while (
            not self._stopping_condition.is_fulfilled()
            and test_suite.get_fitness() != 0.0
        ):
            candidate = self._get_random_solution()
            self._archive.update([candidate])
            test_suite = self._notify_iteration()
            self._current_iteration += 1
        stat.track_output_variable(
            RuntimeVariable.AlgorithmIterations, self._current_iteration
        )
        return self.create_test_suite(self._archive.solutions)

    def _get_random_solution(self) -> tcc.TestCaseChromosome:
        solution = self._chromosome_factory.get_chromosome()
        for fitness_function in self._fitness_functions:
            solution.add_fitness_function(fitness_function)
        return solution

    def _notify_iteration(self) -> tsc.TestSuiteChromosome:
        test_suite = self.create_test_suite(self._archive.solutions)
        stat.current_individual(test_suite)
        coverage = test_suite.get_coverage()
        self._logger.info(
            "Generation: %5i. Coverage: %5f",
            self._current_iteration,
            coverage,
        )
        return cast(tsc.TestSuiteChromosome, test_suite)
