#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides a whole-suite test generation algorithm similar to EvoSuite."""
import logging
from typing import List

from ordered_set import OrderedSet

import pynguin.configuration as config
import pynguin.ga.fitnessfunction as ff
import pynguin.ga.testcasechromosome as tcc
import pynguin.ga.testsuitechromosome as tsc
from pynguin.generation.algorithms.archive import Archive
from pynguin.generation.algorithms.testgenerationstrategy import TestGenerationStrategy
from pynguin.utils import randomness
from pynguin.utils.exceptions import ConstructionFailedException


# pylint: disable=too-few-public-methods
class WholeSuiteTestStrategy(TestGenerationStrategy):
    """Implements a whole-suite test generation algorithm similar to EvoSuite."""

    _logger = logging.getLogger(__name__)

    def __init__(self) -> None:
        super().__init__()
        self._population: List[tsc.TestSuiteChromosome] = []
        self._archive: Archive[ff.FitnessFunction, tcc.TestCaseChromosome]

    def generate_tests(
        self,
    ) -> tsc.TestSuiteChromosome:
        self.before_search_start()
        # These fitness functions are to fine grained...
        self._archive = Archive(OrderedSet(self._test_case_fitness_functions))
        # TODO(fk) update suite fitness function with covered goals
        # TODO(fk) reuse test cases from archive
        # TODO(fk) restrict test cluster to elements that are not fully covered.
        self._population = self._get_random_population()
        self._sort_population()
        self._update_archive()
        suite = self.create_test_suite(self._archive.solutions)
        self.before_first_search_iteration(suite)
        while self.resources_left() and suite.get_fitness() != 0.0:
            self.evolve()
            self._update_archive()
            suite = self.create_test_suite(self._archive.solutions)
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
                if (
                    randomness.next_float()
                    <= config.configuration.search_algorithm.crossover_rate
                ):
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
                fitness_offspring == fitness_parents
                and length_offspring <= length_parents
            ):
                for offspring in [offspring1, offspring2]:
                    if offspring.length() <= 2 * best_individual.length():
                        new_generation.append(offspring)
                    else:
                        new_generation.append(randomness.choice([parent1, parent2]))
            else:
                new_generation.append(parent1)
                new_generation.append(parent2)

        self._population = new_generation
        self._sort_population()

    def _get_random_population(self) -> List[tsc.TestSuiteChromosome]:
        population = []
        for _ in range(config.configuration.search_algorithm.population):
            chromosome = self._chromosome_factory.get_chromosome()
            population.append(chromosome)
        return population

    def _update_archive(self) -> None:
        """Store covering test cases in archive."""
        for suite in self._population:
            self._archive.update(suite.test_case_chromosomes)

    def _sort_population(self) -> None:
        """Sort the population by fitness."""
        self._population.sort(key=lambda x: x.get_fitness())

    def _get_best_individual(self) -> tsc.TestSuiteChromosome:
        """Get the currently best individual.

        Returns:
            The best chromosome
        """
        return self._population[0]

    @staticmethod
    def is_next_population_full(population: List[tsc.TestSuiteChromosome]) -> bool:
        """Check if the population is already full.

        Args:
            population: The list of chromosomes, i.e., the population

        Returns:
            Whether or not the population is already full
        """
        return len(population) >= config.configuration.search_algorithm.population

    def elitism(self) -> List[tsc.TestSuiteChromosome]:
        """Copy best individuals.

        Returns:
            A list of the best chromosomes
        """
        elite = []
        for idx in range(config.configuration.search_algorithm.elite):
            elite.append(self._population[idx].clone())
        return elite
