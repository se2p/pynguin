#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides a random test generator, that creates random test suites."""
import logging

import pynguin.ga.testsuitechromosome as tsc
from pynguin.generation.algorithms.testgenerationstrategy import TestGenerationStrategy


# pylint: disable=too-few-public-methods
class RandomTestSuiteSearchStrategy(TestGenerationStrategy):
    """Create random test suites."""

    _logger = logging.getLogger(__name__)

    def generate_tests(
        self,
    ) -> tsc.TestSuiteChromosome:
        self.before_search_start()
        solution = self._chromosome_factory.get_chromosome()
        self.before_first_search_iteration(solution)
        while self.resources_left() and solution.get_fitness() != 0.0:
            candidate = self._chromosome_factory.get_chromosome()
            if candidate.get_fitness() < solution.get_fitness():
                solution = candidate
            self.after_search_iteration(solution)
        self.after_search_finish()
        return solution


class RandomTestCaseSearchStrategy(TestGenerationStrategy):
    """Creates random test suites based on test-case chromosomes."""

    _logger = logging.getLogger(__name__)

    def generate_tests(self) -> tsc.TestSuiteChromosome:
        self.before_search_start()
        solution = self._chromosome_factory.get_chromosome()
        self._archive.update([solution])
        test_suite = self.create_test_suite(self._archive.solutions)
        self.before_first_search_iteration(test_suite)
        while self.resources_left() and test_suite.get_fitness() != 0.0:
            candidate = self._chromosome_factory.get_chromosome()
            self._archive.update([candidate])
            test_suite = self.create_test_suite(self._archive.solutions)
            self.after_search_iteration(test_suite)
        self.after_search_finish()
        return self.create_test_suite(self._archive.solutions)
