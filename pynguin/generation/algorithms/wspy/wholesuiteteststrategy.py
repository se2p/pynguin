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
from typing import Tuple, List
import pynguin.testsuite.testsuitechromosome as tsc
import pynguin.ga.chromosomefactory as cf
import pynguin.ga.testcasefactory as tcf
import pynguin.configuration as config
from pynguin.ga.fitnessfunctions.branchdistancesuitefitness import (
    BranchDistanceSuiteFitnessFunction,
)
from pynguin.ga.operators.crossover.crossover import CrossOverFunction
from pynguin.ga.operators.crossover.singlepointrelativecrossover import (
    SinglePointRelativeCrossOver,
)
from pynguin.ga.operators.selection.rankselection import RankSelection
from pynguin.ga.operators.selection.selection import SelectionFunction

from pynguin.generation.algorithms.testgenerationstrategy import TestGenerationStrategy
from pynguin.setup.testcluster import TestCluster


# pylint: disable=too-few-public-methods
from pynguin.testcase.execution.testcaseexecutor import TestCaseExecutor
from pynguin.utils import randomness
from pynguin.utils.exceptions import ConstructionFailedException


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
        self._fitness_function = BranchDistanceSuiteFitnessFunction(executor)

    def generate_sequences(
        self,
    ) -> Tuple[tsc.TestSuiteChromosome, tsc.TestSuiteChromosome]:
        stopping_condition = self.get_stopping_condition()
        stopping_condition.reset()
        self._population = self._get_random_population()
        self._sort_population()
        generation = 0
        while (
            not self.is_fulfilled(stopping_condition)
            and self._population[0].get_fitness() != 0.0
        ):
            # TODO(fk) add proper reporting for statistics.
            self._logger.info("Current generation %s", generation)
            self._logger.info(
                "Current best fitness 1. %s", self._population[0].get_fitness()
            )
            self._logger.info(
                "Current best fitness 2. %s", self._population[1].get_fitness()
            )
            self._logger.info(
                "Current best fitness 3. %s", self._population[2].get_fitness()
            )
            self.evolve()
            generation += 1
        self._logger.info("Found solution")
        self._logger.info("Current generation %s", generation)
        self._logger.info(
            "Current best fitness 1. %s", self._population[0].get_fitness()
        )
        self._logger.info(
            "Current best fitness 2. %s", self._population[1].get_fitness()
        )
        self._logger.info(
            "Current best fitness 3. %s", self._population[2].get_fitness()
        )
        return self._population[0], tsc.TestSuiteChromosome()

    def evolve(self):
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

            f_p = min(parent1.get_fitness(), parent2.get_fitness())
            f_o = min(offspring1.get_fitness(), offspring2.get_fitness())
            l_p = (
                parent1.total_length_of_test_cases + parent2.total_length_of_test_cases
            )
            l_o = (
                offspring1.total_length_of_test_cases
                + offspring2.total_length_of_test_cases
            )
            t_b = self._population[0]

            if (f_o < f_p) or (f_o == f_p and l_o <= l_p):
                for offspring in [offspring1, offspring2]:
                    if (
                        offspring.total_length_of_test_cases
                        <= 2 * t_b.total_length_of_test_cases
                    ):
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
        for _ in range(config.INSTANCE.population):
            chromosome = self._chromosome_factory.get_chromosome()
            chromosome.add_fitness_function(self._fitness_function)
            population.append(chromosome)
        return population

    def _sort_population(self):
        self._population.sort(key=lambda x: x.get_fitness())

    @staticmethod
    def is_next_population_full(population: List[tsc.TestSuiteChromosome]) -> bool:
        """Check if the population is already full."""
        return len(population) >= config.INSTANCE.population

    def elitism(self) -> List[tsc.TestSuiteChromosome]:
        """Copy best individuals."""
        elite = []
        for idx in range(config.INSTANCE.elite):
            elite.append(self._population[idx].clone())
        return elite
