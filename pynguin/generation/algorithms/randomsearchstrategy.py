#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides a random test generator, that creates random test suites."""
import logging

from ordered_set import OrderedSet

import pynguin.ga.fitnessfunction as ff
import pynguin.ga.testcasechromosome as tcc
import pynguin.ga.testsuitechromosome as tsc
from pynguin.generation.algorithms.archive import Archive
from pynguin.generation.algorithms.testgenerationstrategy import TestGenerationStrategy
from pynguin.generation.algorithms.wraptestsuitemixin import WrapTestSuiteMixin


# pylint: disable=too-few-public-methods
class RandomTestSuiteSearchStrategy(TestGenerationStrategy):
    """Create random test suites."""

    _logger = logging.getLogger(__name__)

    def generate_tests(
        self,
    ) -> tsc.TestSuiteChromosome:
        self.before_search_start()
        solution = self._get_random_solution()
        self.before_first_search_iteration(solution)
        while self.resources_left() and solution.get_fitness() != 0.0:
            candidate = self._get_random_solution()
            if candidate.get_fitness() < solution.get_fitness():
                solution = candidate
            self.after_search_iteration(solution)
        self.after_search_finish()
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

    def generate_tests(self) -> tsc.TestSuiteChromosome:
        self.before_search_start()
        archive: Archive[ff.FitnessFunction, tcc.TestCaseChromosome] = Archive(
            OrderedSet(self._fitness_functions)
        )
        solution = self._get_random_solution()
        archive.update([solution])
        test_suite = self.create_test_suite(archive.solutions)
        self.before_first_search_iteration(test_suite)
        while self.resources_left() and test_suite.get_fitness() != 0.0:
            candidate = self._get_random_solution()
            archive.update([candidate])
            test_suite = self.create_test_suite(archive.solutions)
            self.after_search_iteration(test_suite)
        self.after_search_finish()
        return self.create_test_suite(archive.solutions)

    def _get_random_solution(self) -> tcc.TestCaseChromosome:
        solution = self._chromosome_factory.get_chromosome()
        for fitness_function in self._fitness_functions:
            solution.add_fitness_function(fitness_function)
        return solution
