#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2024 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides an abstract base class for MOSA and its derivatives."""

from __future__ import annotations

import logging

from abc import ABC
from typing import cast

import pynguin.configuration as config
import pynguin.ga.testcasechromosome as tcc

from pynguin.ga.algorithms.archive import CoverageArchive
from pynguin.ga.algorithms.generationalgorithm import GenerationAlgorithm
from pynguin.ga.operators.comparator import DominanceComparator
from pynguin.utils import randomness
from pynguin.utils.exceptions import ConstructionFailedException


class AbstractMOSAAlgorithm(GenerationAlgorithm[CoverageArchive], ABC):
    """An abstract base implementation for MOSA and its derivatives."""

    _logger = logging.getLogger(__name__)

    def __init__(self) -> None:  # noqa: D107
        super().__init__()
        self._population: list[tcc.TestCaseChromosome] = []
        self._number_of_goals = -1

    def _breed_next_generation(self) -> list[tcc.TestCaseChromosome]:  # noqa: C901
        offspring_population: list[tcc.TestCaseChromosome] = []
        for _ in range(int(config.configuration.search_algorithm.population / 2)):
            parent_1 = self._selection_function.select(self._population)[0]
            parent_2 = self._selection_function.select(self._population)[0]
            offspring_1 = cast(tcc.TestCaseChromosome, parent_1.clone())
            offspring_2 = cast(tcc.TestCaseChromosome, parent_2.clone())

            # Apply crossover
            if randomness.next_float() <= config.configuration.search_algorithm.crossover_rate:
                try:
                    self._crossover_function.cross_over(offspring_1, offspring_2)
                except ConstructionFailedException:
                    self._logger.debug("CrossOver failed.")
                    continue

            # Apply mutation on offspring_1
            for _ in range(config.configuration.search_algorithm.number_of_mutations):
                self._mutate(offspring_1)
            if offspring_1.changed and offspring_1.size() > 0:
                offspring_population.append(offspring_1)

            # Apply mutation on offspring_2
            for _ in range(config.configuration.search_algorithm.number_of_mutations):
                self._mutate(offspring_2)
            if offspring_2.changed and offspring_2.size() > 0:
                offspring_population.append(offspring_2)

        # Add new randomly generated tests
        for _ in range(
            int(
                config.configuration.search_algorithm.population
                * config.configuration.search_algorithm.test_insertion_probability
            )
        ):
            if len(self._archive.covered_goals) == 0 or randomness.next_bool():
                tch: tcc.TestCaseChromosome = self._chromosome_factory.get_chromosome()
            else:
                tch = randomness.choice(self._archive.solutions).clone()
                tch.mutate()

            if tch.changed and tch.size() > 0:
                offspring_population.append(tch)

        self._logger.debug("Number of offsprings = %d", len(offspring_population))
        return offspring_population

    @staticmethod
    def _mutate(offspring: tcc.TestCaseChromosome) -> None:
        offspring.mutate()
        if not offspring.changed:
            # if offspring is not changed, we try to mutate it once again
            offspring.mutate()

    def _get_non_dominated_solutions(
        self, solutions: list[tcc.TestCaseChromosome]
    ) -> list[tcc.TestCaseChromosome]:
        comparator: DominanceComparator[tcc.TestCaseChromosome] = DominanceComparator(
            goals=self._archive.covered_goals  # type: ignore[arg-type]
        )
        next_front: list[tcc.TestCaseChromosome] = []
        for solution in solutions:
            is_dominated = False
            dominated_solutions: list[tcc.TestCaseChromosome] = []
            for best in next_front:
                flag = comparator.compare(solution, best)
                if flag < 0:
                    dominated_solutions.append(best)
                if flag > 0:
                    is_dominated = True
            if is_dominated:
                continue
            next_front.append(solution)
            for dominated_solution in dominated_solutions:
                if dominated_solution in next_front:
                    next_front.remove(dominated_solution)
        return next_front

    def _get_random_population(self) -> list[tcc.TestCaseChromosome]:
        population: list[tcc.TestCaseChromosome] = []
        for _ in range(config.configuration.search_algorithm.population):
            chromosome = self._chromosome_factory.get_chromosome()
            population.append(chromosome)
        return population

    def _get_best_individuals(self) -> list[tcc.TestCaseChromosome]:
        return self._get_non_dominated_solutions(self._population)
