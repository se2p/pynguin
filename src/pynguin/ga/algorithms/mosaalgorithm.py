# This file is part of Pynguin.
#
# SPDX-FileCopyrightText: 2019–2024 Pynguin Contributors
#
# SPDX-License-Identifier: MIT
#
"""Provides the MOSA test-generation strategy."""
from __future__ import annotations

import logging

from typing import TYPE_CHECKING

import pynguin.ga.computations as ff
import pynguin.utils.statistics.statistics as stat

from pynguin.ga.algorithms.abstractmosaalgorithm import AbstractMOSAAlgorithm
from pynguin.ga.operators.ranking import fast_epsilon_dominance_assignment
from pynguin.utils.orderedset import OrderedSet
from pynguin.utils.statistics.runtimevariable import RuntimeVariable


if TYPE_CHECKING:
    import pynguin.ga.testcasechromosome as tcc
    import pynguin.ga.testsuitechromosome as tsc


class MOSAAlgorithm(AbstractMOSAAlgorithm):
    """Implements the Many-Objective Sorting Algorithm MOSA."""

    _logger = logging.getLogger(__name__)

    def __init__(self) -> None:
        super().__init__()
        self.current_iteration = 0

    def generate_tests(self) -> tsc.TestSuiteChromosome:
        self.before_search_start()
        self._number_of_goals = len(self._test_case_fitness_functions)
        stat.set_output_variable_for_runtime_variable(
            RuntimeVariable.Goals, self._number_of_goals
        )

        self._population = self._get_random_population()
        self._archive.update(self._population)

        # Calculate dominance ranks and crowding distance
        fronts = self._ranking_function.compute_ranking_assignment(
            self._population, self._archive.uncovered_goals  # type: ignore[arg-type]
        )
        for i in range(fronts.get_number_of_sub_fronts()):
            fast_epsilon_dominance_assignment(
                fronts.get_sub_front(i),
                self._archive.uncovered_goals,  # type: ignore[arg-type]
            )

        self.before_first_search_iteration(
            self.create_test_suite(self._archive.solutions)
        )
        while (
            self.resources_left()
            and self._number_of_goals - len(self._archive.covered_goals) != 0
        ):
            self.evolve()
            self.after_search_iteration(self.create_test_suite(self._archive.solutions))

        self.after_search_finish()
        return self.create_test_suite(
            self._archive.solutions
            if len(self._archive.solutions) > 0
            else self._get_best_individuals()
        )

    def evolve(self) -> None:
        """Runs one evolution step."""
        offspring_population: list[tcc.TestCaseChromosome] = (
            self._breed_next_generation()
        )

        # Create union of parents and offspring
        union: list[tcc.TestCaseChromosome] = []
        union.extend(self._population)
        union.extend(offspring_population)

        uncovered_goals: OrderedSet[
            ff.FitnessFunction
        ] = self._archive.uncovered_goals  # type: ignore[assignment]

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
            self._population.extend(front[k] for k in range(remain))

        self._archive.update(self._population)

        # Log after evolution
        self.log_iteration()

        self.current_iteration += 1

    def log_iteration(self):
        self.log_population("population", self._population)
        self.log_goals()
        self.log_archive()

    def log_population(self, name, population):
        current_population = f'\n"{name}": {{"iteration": {self.current_iteration}, "individuals": {self.population_log_string(population)}}}\n'
        self._logger.info(current_population)

    def log_goals(self):
        goalsstr = f'\n"Goals": {{"iteration": {self.current_iteration}, "uncovered": {len(self._archive.uncovered_goals)}, "covered": {len(self._archive.covered_goals)}, "covered targets": ['
        goalsstr += ", ".join([f'"{tff}"' for tff in self._archive.covered_goals])
        goalsstr += '],\n"current targets": ['
        goalsstr += ", ".join([f'"{tff}"' for tff in self._archive.current_goals])
        goalsstr += ']}\n'
        goalsstr += f'\n"Chromosome Goals": {{"iteration": {self.current_iteration}, "individuals": ['
        for tc in self._population:
            goalsstr += f'\n{{"id": "{tc.get_id()}", "goals": ['
            goalsstr += ", ".join([f'{{"fitness": "{entry.value}", "goal": "{entry.key}"}}' for entry in tc.fitness_values.items()])
            goalsstr += ']}\n},'
        goalsstr = goalsstr.rstrip(',')  # Remove the trailing comma
        goalsstr += '\n]}\n'
        self._logger.info(goalsstr)

    def log_archive(self):
        archive_str = f'\n"Archive": {{"iteration": {self.current_iteration}, "solutions": ['
        archive_str += ", ".join([f'"{tc.get_id()}"' for tc in self._archive.solutions])
        archive_str += ']}}\n'
        self._logger.info(archive_str)
