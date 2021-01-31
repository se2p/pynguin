#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#

#  This file is part of Pynguin.
#
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides the MOSA test-generation strategy."""
import logging
from typing import List, Set

import pynguin.ga.chromosome as chrom
import pynguin.ga.fitnessfunction as ff
import pynguin.ga.testcasechromosome as tcc
import pynguin.utils.statistics.statistics as stat
from pynguin.ga.operators.ranking.crowdingdistance import (
    fast_epsilon_dominance_assignment,
)
from pynguin.generation.algorithms.abstractmosastrategy import AbstractMOSATestStrategy
from pynguin.generation.algorithms.archive import Archive
from pynguin.utils.statistics.runtimevariable import RuntimeVariable


# pylint: disable=too-many-instance-attributes
class MOSATestStrategy(AbstractMOSATestStrategy):
    """Implements the Many-Objective Sorting Algorithm MOSA."""

    _logger = logging.getLogger(__name__)

    def generate_tests(self) -> chrom.Chromosome:
        self._logger.info("Start generating tests")
        self._archive = Archive(set(self._fitness_functions))
        self._number_of_goals = len(self._fitness_functions)
        stat.set_output_variable_for_runtime_variable(
            RuntimeVariable.Goals, self._number_of_goals
        )

        self._current_iteration = 0
        self._population = self._get_random_population()
        self._archive.update(self._population)

        # Calculate dominance ranks and crowding distance
        fronts = self._ranking_function.compute_ranking_assignment(
            self._population, self._archive.uncovered_goals
        )
        for i in range(fronts.get_number_of_sub_fronts()):
            fast_epsilon_dominance_assignment(
                fronts.get_sub_front(i), self._archive.uncovered_goals
            )

        while (
            not self._stopping_condition.is_fulfilled()
            and self._number_of_goals - len(self._archive.covered_goals) != 0
        ):
            self.evolve()
            self._notify_iteration()
            self._current_iteration += 1

        stat.track_output_variable(
            RuntimeVariable.AlgorithmIterations, self._current_iteration
        )
        return self.create_test_suite(
            self._archive.solutions
            if len(self._archive.solutions) > 0
            else self._get_best_individuals()
        )

    def evolve(self) -> None:
        """Runs one evolution step."""
        offspring_population: List[
            tcc.TestCaseChromosome
        ] = self._breed_next_generation()

        # Create union of parents and offspring
        union: List[tcc.TestCaseChromosome] = []
        union.extend(self._population)
        union.extend(offspring_population)

        uncovered_goals: Set[ff.FitnessFunction] = self._archive.uncovered_goals

        # Ranking the union
        self._logger.debug("Union Size = %d", len(union))
        # Ranking the union using the best rank algorithm
        fronts = self._ranking_function.compute_ranking_assignment(
            union, uncovered_goals
        )

        remain = len(self._population)
        index = 0
        self._population.clear()

        # Obtain the next front
        front = fronts.get_sub_front(index)

        while remain > 0 and remain >= len(front) != 0:
            # Assign crowding distance to individuals
            fast_epsilon_dominance_assignment(front, uncovered_goals)
            # Add the individuals of this front
            self._population.extend(front)
            # Decrement remain
            remain -= len(front)
            # Obtain the next front
            index += 1
            if remain > 0:
                front = fronts.get_sub_front(index)

        # Remain is less than len(front[index]), insert only the best one
        if remain > 0 and len(front) != 0:
            fast_epsilon_dominance_assignment(front, uncovered_goals)
            front.sort(key=lambda t: t.distance, reverse=True)
            for k in range(remain):
                self._population.append(front[k])

        self._archive.update(self._population)

    def _notify_iteration(self) -> None:
        coverage = len(self._archive.covered_goals) / self._number_of_goals
        self._logger.info(
            "Generation: %5i. Coverage: %5f",
            self._current_iteration,
            coverage,
        )
        stat.update_output_variable_for_runtime_variable(
            RuntimeVariable.CoverageTimeline, coverage
        )
