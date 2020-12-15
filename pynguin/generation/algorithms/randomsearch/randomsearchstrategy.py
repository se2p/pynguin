#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides a random test generator, that creates random test suites."""
import logging

import pynguin.ga.testcasechromosomefactory as tccf
import pynguin.ga.testcasefactory as tcf
import pynguin.ga.testsuitechromosome as tsc
import pynguin.ga.testsuitechromosomefactory as tscf
import pynguin.testcase.testfactory as tf
from pynguin.generation.algorithms.testgenerationstrategy import TestGenerationStrategy
from pynguin.setup.testcluster import TestCluster
from pynguin.testcase.execution.testcaseexecutor import TestCaseExecutor
from pynguin.utils.statistics.statistics import RuntimeVariable, StatisticsTracker


# pylint: disable=too-few-public-methods
class RandomSearchStrategy(TestGenerationStrategy):
    """Create random test suites."""

    _logger = logging.getLogger(__name__)

    def __init__(
        self,
        executor: TestCaseExecutor,
        test_cluster: TestCluster,
        test_factory: tf.TestFactory,
        test_case_factory: tcf.TestCaseFactory,
    ) -> None:
        super().__init__(executor, test_cluster, test_factory)
        self._chromosome_factory = tscf.TestSuiteChromosomeFactory(
            tccf.TestCaseChromosomeFactory(self._test_factory, test_case_factory)
        )
        self._fitness_functions = self.get_fitness_functions()

    def generate_tests(
        self,
    ) -> tsc.TestSuiteChromosome:
        stopping_condition = self.get_stopping_condition()
        stopping_condition.reset()
        solution = self._get_random_solution()
        StatisticsTracker().current_individual(solution)
        generation = 0
        while (
            not self.is_fulfilled(stopping_condition) and solution.get_fitness() != 0.0
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
            StatisticsTracker().current_individual(solution)
            generation += 1
        StatisticsTracker().track_output_variable(
            RuntimeVariable.AlgorithmIterations, generation
        )
        return solution

    def _get_random_solution(self) -> tsc.TestSuiteChromosome:
        """Small helper to create new solution and add fitness functions."""
        solution = self._chromosome_factory.get_chromosome()
        for fitness_function in self._fitness_functions:
            solution.add_fitness_function(fitness_function)

        return solution
