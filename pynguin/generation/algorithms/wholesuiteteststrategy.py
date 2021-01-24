#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides a whole-suite test generation algorithm similar to EvoSuite."""
import logging
from typing import List

import pynguin.configuration as config
import pynguin.ga.testsuitechromosome as tsc
import pynguin.utils.statistics.statistics as stat
from pynguin.generation.algorithms.testgenerationstrategy import TestGenerationStrategy
from pynguin.utils import randomness
from pynguin.utils.exceptions import ConstructionFailedException
from pynguin.utils.statistics.runtimevariable import RuntimeVariable


# pylint: disable=too-few-public-methods
class WholeSuiteTestStrategy(TestGenerationStrategy):
    """Implements a whole-suite test generation algorithm similar to EvoSuite."""

    _logger = logging.getLogger(__name__)

    def __init__(self) -> None:
        super().__init__()
        self._population: List[tsc.TestSuiteChromosome] = []

    def generate_tests(
        self,
    ) -> tsc.TestSuiteChromosome:
        self._population = self._get_random_population()
        self._sort_population()
        stat.current_individual(self._get_best_individual())
        generation = 0
        while (
            not self._stopping_condition.is_fulfilled()
            and self._get_best_individual().get_fitness() != 0.0
        ):
            self.evolve()
            stat.current_individual(self._get_best_individual())
            self._logger.info(
                "Generation: %5i. Best fitness: %5f, Best coverage %5f",
                generation,
                self._get_best_individual().get_fitness(),
                self._get_best_individual().get_coverage(),
            )
            generation += 1
        stat.track_output_variable(RuntimeVariable.AlgorithmIterations, generation)
        best = self._get_best_individual()
        # Make sure all test cases have a cached result.
        best.get_fitness()
        return best

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
                if randomness.next_float() <= config.configuration.crossover_rate:
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
        stat.current_individual(self._get_best_individual())

    def _get_random_population(self) -> List[tsc.TestSuiteChromosome]:
        population = []
        for _ in range(config.configuration.population):
            chromosome = self._chromosome_factory.get_chromosome()
            for fitness_function in self._fitness_functions:
                chromosome.add_fitness_function(fitness_function)
            population.append(chromosome)
        return population

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
        return len(population) >= config.configuration.population

    def elitism(self) -> List[tsc.TestSuiteChromosome]:
        """Copy best individuals.

        Returns:
            A list of the best chromosomes
        """
        elite = []
        for idx in range(config.configuration.elite):
            elite.append(self._population[idx].clone())
        return elite
