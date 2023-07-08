#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2023 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides a random test generator, that creates random test suites."""
from __future__ import annotations

import logging

from typing import TYPE_CHECKING

from pynguin.ga.algorithms.generationalgorithm import GenerationAlgorithm

import pynguin.configuration as config

if TYPE_CHECKING:
    import pynguin.ga.testsuitechromosome as tsc


class RandomTestSuiteSearchAlgorithm(GenerationAlgorithm):
    """Create random test suites."""

    _logger = logging.getLogger(__name__)

    def generate_tests(self) -> tsc.TestSuiteChromosome:  # noqa: D102
        self.before_search_start()
        solution = self._chromosome_factory.get_chromosome()
        self.before_first_search_iteration(solution)
        coverageCache = 0
        coverageCounter = 1
        minCov = config.configuration.stopping.minimum_coverage_quick
        minIter = config.configuration.stopping.minimum_iteration_quick
        while self.resources_left() and solution.get_fitness() != 0.0:
            candidate = self._chromosome_factory.get_chromosome()
            if candidate.get_fitness() < solution.get_fitness():
                solution = candidate
            self.after_search_iteration(solution)
            #The following checks if minimum coverage is reached, only if minimum-coverage-quick is below 1.0
            if minCov < 1.0:
                if solution.get_coverage() == coverageCache and coverageCache => minCov:
                    if coverageCounter >= minIter:
                        break
                    else:
                        coverageCounter = coverageCounter +1
                else:
                    coverageCache = solution.get_coverage()
                    coverageCounter = 1
        self.after_search_finish()
        return solution


class RandomTestCaseSearchAlgorithm(GenerationAlgorithm):
    """Creates random test suites based on test-case chromosomes."""

    _logger = logging.getLogger(__name__)

    def generate_tests(self) -> tsc.TestSuiteChromosome:  # noqa: D102
        self.before_search_start()
        solution = self._chromosome_factory.get_chromosome()
        self._archive.update([solution])
        test_suite = self.create_test_suite(self._archive.solutions)
        self.before_first_search_iteration(test_suite)
        coverageCache = 0
        coverageCounter = 1
        minCov = config.configuration.stopping.minimum_coverage_quick
        minIter = config.configuration.stopping.minimum_iteration_quick
        while self.resources_left() and test_suite.get_fitness() != 0.0:
            candidate = self._chromosome_factory.get_chromosome()
            self._archive.update([candidate])
            test_suite = self.create_test_suite(self._archive.solutions)
            self.after_search_iteration(test_suite)
            #The following checks if minimum coverage is reached, only if minimum-coverage-quick is below 1.0
            if minCov < 1.0:
                if test_suite.get_coverage() == coverageCache and coverageCache => minCov:
                    if coverageCounter >= minIter:
                        break
                    else:
                        coverageCounter = coverageCounter +1
                else:
                    coverageCache = test_suite.get_coverage()
                    coverageCounter = 1
        self.after_search_finish()
        return self.create_test_suite(self._archive.solutions)
