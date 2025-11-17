#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides a whole-suite test generation algorithm similar to EvoSuite."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, cast

import pynguin.configuration as config
import pynguin.ga.algorithms.archive as arch
import pynguin.ga.computations as ff
import pynguin.ga.coveragegoals as bg
from pynguin.ga.algorithms.generationalgorithm import GenerationAlgorithm
from pynguin.utils import randomness
from pynguin.utils.exceptions import ConstructionFailedException

if TYPE_CHECKING:
    import pynguin.ga.testsuitechromosome as tsc

# TODO(fk) instead of switching on 'use_archive' on two locations, we could
# also create another subclass?


class WholeSuiteAlgorithm(GenerationAlgorithm[arch.CoverageArchive]):
    """Implements a whole-suite test generation algorithm similar to EvoSuite."""

    _logger = logging.getLogger(__name__)

    def __init__(self) -> None:  # noqa: D107
        super().__init__()
        self._population: list[tsc.TestSuiteChromosome] = []

    def generate_tests(  # noqa: D102
        self,
    ) -> tsc.TestSuiteChromosome:
        self.before_search_start()
        self._population = self._get_random_population()
        self._update_archive()
        self._sort_population()
        suite = self._get_solution()
        self.before_first_search_iteration(suite)
        while self.resources_left() and suite.get_fitness() != 0.0:
            self.evolve()
            suite = self._get_solution()
            self.after_search_iteration(suite)
        self.after_search_finish()
        return suite

    def evolve(self) -> None:
        """Evolve the current population and replace it with a new one."""
        new_generation = []
        new_generation.extend(self.elitism())
        while not self.is_next_population_full(new_generation):
            parent1 = self._selection_function.select(self._population, 1)[0]
            parent2 = self._selection_function.select(self._population, 1)[0]

            offspring1 = parent1.clone()
            offspring2 = parent2.clone()

            try:
                if randomness.next_float() <= config.configuration.search_algorithm.crossover_rate:
                    self._crossover_function.cross_over(offspring1, offspring2)

                offspring1.mutate()
                offspring2.mutate()
            except ConstructionFailedException as ex:
                self._logger.info("Crossover/Mutation failed: %s", ex)
                continue

            fitness_parents = min(parent1.get_fitness(), parent2.get_fitness())
            fitness_offspring = min(offspring1.get_fitness(), offspring2.get_fitness())
            length_parents = parent1.length() + parent2.length()
            length_offspring = offspring1.length() + offspring2.length()
            best_individual = self._get_best_individual()

            if (fitness_offspring < fitness_parents) or (
                fitness_offspring == fitness_parents and length_offspring <= length_parents
            ):
                for offspring in [offspring1, offspring2]:
                    if offspring.length() <= 2 * best_individual.length():
                        new_generation.append(offspring)
                    else:
                        new_generation.append(randomness.choice((parent1, parent2)))
            else:
                new_generation.extend((parent1, parent2))

        self._population = new_generation
        self._update_archive()
        self._sort_population()

    def _get_random_population(self) -> list[tsc.TestSuiteChromosome]:
        population = []
        for _ in range(config.configuration.search_algorithm.population):
            chromosome = self._chromosome_factory.get_chromosome()
            population.append(chromosome)
        return population

    def _update_archive(self) -> None:
        """Store covering test cases in archive."""
        if not config.configuration.search_algorithm.use_archive:
            return

        before = len(self._archive.uncovered_goals)
        for suite in self._population:
            self._archive.update(suite.test_case_chromosomes)
        # New goals were covered
        if before != len(self._archive.uncovered_goals):
            exclude_code: set[int] = set()
            exclude_true: set[int] = set()
            exclude_false: set[int] = set()

            # TODO(fk) Move this logic to BranchCoverageTestFitness?
            # i.e. combine with Archive.add_on_target_covered()
            for covered in self._archive.covered_goals:
                assert isinstance(covered, bg.BranchCoverageTestFitness)
                goal = covered.goal
                if goal.is_branchless_code_object:
                    exclude_code.add(goal.code_object_id)
                elif goal.is_branch:
                    branch_goal = cast("bg.BranchGoal", goal)
                    if branch_goal.value:
                        exclude_true.add(branch_goal.predicate_id)
                    else:
                        exclude_false.add(branch_goal.predicate_id)
                else:
                    raise ValueError("Unknown coverage goal")

            for func in self.test_suite_fitness_functions:
                assert isinstance(func, ff.BranchDistanceTestSuiteFitnessFunction)
                func.restrict(exclude_code, exclude_true, exclude_false)
            # Force re-computation of fitness.
            for chromosome in self._population:
                chromosome.invalidate_cache()

    def _sort_population(self) -> None:
        """Sort the population by fitness."""
        self._population.sort(key=lambda x: x.get_fitness())

    def _get_best_individual(self) -> tsc.TestSuiteChromosome:
        """Get the currently best individual.

        Returns:
            The best chromosome
        """
        return self._population[0]

    def _get_solution(self) -> tsc.TestSuiteChromosome:
        """Get the solution."""
        if config.configuration.search_algorithm.use_archive:
            # If we use an archive, use the best found solutions.
            return self.create_test_suite(self._archive.solutions)
        # If we don't use an archive, use the current best individual.
        return self._get_best_individual()

    @staticmethod
    def is_next_population_full(population: list[tsc.TestSuiteChromosome]) -> bool:
        """Check if the population is already full.

        Args:
            population: The list of chromosomes, i.e., the population

        Returns:
            Whether or not the population is already full
        """
        return len(population) >= config.configuration.search_algorithm.population

    def elitism(self) -> list[tsc.TestSuiteChromosome]:
        """Copy best individuals.

        Returns:
            A list of the best chromosomes
        """
        return [
            self._population[idx].clone()
            for idx in range(config.configuration.search_algorithm.elite)
        ]
