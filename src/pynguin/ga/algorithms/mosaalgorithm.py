#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides the MOSA test-generation strategy."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pynguin.utils.statistics.stats as stat
from pynguin.ga.algorithms.abstractmosaalgorithm import AbstractMOSAAlgorithm
from pynguin.ga.operators.ranking import fast_epsilon_dominance_assignment
from pynguin.utils.statistics.runtimevariable import RuntimeVariable

if TYPE_CHECKING:
    import pynguin.ga.testsuitechromosome as tsc


class MOSAAlgorithm(AbstractMOSAAlgorithm):
    """Implements the Many-Objective Sorting Algorithm MOSA."""

    _logger = logging.getLogger(__name__)

    def _initialize_generation(self) -> None:
        self.before_search_start()
        self._number_of_goals = len(self._test_case_fitness_functions)
        stat.set_output_variable_for_runtime_variable(RuntimeVariable.Goals, self._number_of_goals)

        self._population = self._get_random_population()
        self._archive.update(self._population)

        self._compute_dominance()

        self.before_first_search_iteration(self.create_test_suite(self._archive.solutions))

    def _compute_dominance(self) -> None:
        fronts = self._ranking_function.compute_ranking_assignment(
            self._population,
            self._archive.uncovered_goals,  # type: ignore[arg-type]
        )
        for i in range(fronts.get_number_of_sub_fronts()):
            fast_epsilon_dominance_assignment(
                fronts.get_sub_front(i),
                self._archive.uncovered_goals,  # type: ignore[arg-type]
            )

    def _finalize_generation(self) -> tsc.TestSuiteChromosome:
        self.after_search_finish()
        return self.create_test_suite(
            self._archive.solutions
            if len(self._archive.solutions) > 0
            else self._get_best_individuals()
        )

    def generate_tests(self) -> tsc.TestSuiteChromosome:  # noqa: D102
        self._initialize_generation()
        while (
            self.resources_left() and self._number_of_goals - len(self._archive.covered_goals) != 0
        ):
            self.evolve()
            self.after_search_iteration(self.create_test_suite(self._archive.solutions))

        return self._finalize_generation()
