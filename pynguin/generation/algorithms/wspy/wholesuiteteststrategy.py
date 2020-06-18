# This file is part of Pynguin.
#
# Pynguin is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Pynguin is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Pynguin.  If not, see <https://www.gnu.org/licenses/>.
"""Provides a whole-suite test generation algorithm similar to EvoSuite."""
import logging
from typing import List, Tuple

import pynguin.configuration as config
import pynguin.ga.chromosomefactory as cf
import pynguin.ga.testcasefactory as tcf
import pynguin.testsuite.testsuitechromosome as tsc
from pynguin.ga.operators.crossover.crossover import CrossOverFunction
from pynguin.ga.operators.crossover.singlepointrelativecrossover import (
    SinglePointRelativeCrossOver,
)
from pynguin.ga.operators.selection.rankselection import RankSelection
from pynguin.ga.operators.selection.selection import SelectionFunction
from pynguin.generation.algorithms.testgenerationstrategy import TestGenerationStrategy
from pynguin.setup.testcluster import TestCluster
from pynguin.testcase.execution.testcaseexecutor import TestCaseExecutor
from pynguin.utils import randomness
from pynguin.utils.exceptions import ConstructionFailedException
from pynguin.utils.statistics.statistics import RuntimeVariable, StatisticsTracker


# pylint: disable=too-few-public-methods
class WholeSuiteTestStrategy(TestGenerationStrategy):
    """Implements a whole-suite test generation algorithm similar to EvoSuite."""

    _logger = logging.getLogger(__name__)

    def __init__(self, executor: TestCaseExecutor, test_cluster: TestCluster) -> None:
        super().__init__(executor, test_cluster)
        self._chromosome_factory = cf.TestSuiteChromosomeFactory(
            tcf.RandomLengthTestCaseFactory(self._test_factory)
        )
        self._population: List[tsc.TestSuiteChromosome] = []
        self._selection_function: SelectionFunction[
            tsc.TestSuiteChromosome
        ] = RankSelection()
        self._crossover_function: CrossOverFunction[
            tsc.TestSuiteChromosome
        ] = SinglePointRelativeCrossOver()
        self._fitness_functions = self.get_fitness_functions()

    def generate_sequences(
        self,
    ) -> Tuple[tsc.TestSuiteChromosome, tsc.TestSuiteChromosome]:
        stopping_condition = self.get_stopping_condition()
        stopping_condition.reset()
        self._population = self._get_random_population()
        self._sort_population()
        StatisticsTracker().current_individual(self._get_best_individual())
        generation = 0
        while (
            not self.is_fulfilled(stopping_condition)
            and self._get_best_individual().get_fitness() != 0.0
        ):
            self.evolve()
            StatisticsTracker().current_individual(self._get_best_individual())
            self._logger.info(
                "Generation: %5i. Best fitness: %5f, Best coverage %5f",
                generation,
                self._get_best_individual().get_fitness(),
                self._get_best_individual().get_coverage(),
            )
            generation += 1
        StatisticsTracker().track_output_variable(
            RuntimeVariable.AlgorithmIterations, generation
        )
        return self.split_chromosomes()

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
                if randomness.next_float() <= config.INSTANCE.crossover_rate:
                    self._crossover_function.cross_over(offspring1, offspring2)

                offspring1.mutate()
                offspring2.mutate()
            except ConstructionFailedException as ex:
                self._logger.info("Crossover/Mutation failed: %s", ex)
                continue

            fitness_parents = min(parent1.get_fitness(), parent2.get_fitness())
            fitness_offspring = min(offspring1.get_fitness(), offspring2.get_fitness())
            length_parents = (
                parent1.total_length_of_test_cases + parent2.total_length_of_test_cases
            )
            length_offspring = (
                offspring1.total_length_of_test_cases
                + offspring2.total_length_of_test_cases
            )
            best_individual = self._get_best_individual()

            if (fitness_offspring < fitness_parents) or (
                fitness_offspring == fitness_parents
                and length_offspring <= length_parents
            ):
                for offspring in [offspring1, offspring2]:
                    if (
                        offspring.total_length_of_test_cases
                        <= 2 * best_individual.total_length_of_test_cases
                    ):
                        new_generation.append(offspring)
                    else:
                        new_generation.append(randomness.choice([parent1, parent2]))
            else:
                new_generation.append(parent1)
                new_generation.append(parent2)

        self._population = new_generation
        self._sort_population()
        StatisticsTracker().current_individual(self._get_best_individual())

    def _get_random_population(self) -> List[tsc.TestSuiteChromosome]:
        population = []
        for _ in range(config.INSTANCE.population):
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
        return len(population) >= config.INSTANCE.population

    def elitism(self) -> List[tsc.TestSuiteChromosome]:
        """Copy best individuals.

        Returns:
            A list of the best chromosomes
        """
        elite = []
        for idx in range(config.INSTANCE.elite):
            elite.append(self._population[idx].clone())
        return elite

    def split_chromosomes(
        self,
    ) -> Tuple[tsc.TestSuiteChromosome, tsc.TestSuiteChromosome]:
        """Split the chromosome into two chromosomes.

        The first one contains the non failing test cases.
        The second one contains the failing test cases.

        Returns:
            A tuple of passing and failing chromosomes
        """
        best = self._get_best_individual()
        # Make sure all test cases have a cached result.
        best.get_fitness()
        non_failing = tsc.TestSuiteChromosome()
        failing = tsc.TestSuiteChromosome()

        for fitness_function in self._fitness_functions:
            non_failing.add_fitness_function(fitness_function)
            failing.add_fitness_function(fitness_function)

        for test_case in best.test_chromosomes:
            result = test_case.get_last_execution_result()
            assert result is not None
            if result.has_test_exceptions():
                failing.add_test(test_case.clone())
            else:
                non_failing.add_test(test_case.clone())

        return non_failing, failing
