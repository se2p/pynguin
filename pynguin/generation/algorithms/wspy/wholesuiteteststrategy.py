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
import pynguin.testsuite.testsuitechromosome as tsc

import pynguin.testcase.testcase as tc
import pynguin.testcase.defaulttestcase as dtc
import pynguin.configuration as config
from pynguin.generation.algorithms.testgenerationstrategy import TestGenerationStrategy
from pynguin.testcase.execution.abstractexecutor import AbstractExecutor


# pylint: disable=too-few-public-methods
from pynguin.utils import randomness


class WholeSuiteTestStrategy(TestGenerationStrategy):
    """Implements a whole-suite test generation algorithm similar to EvoSuite."""

    _logger = logging.getLogger(__name__)

    def __init__(self, executor: AbstractExecutor) -> None:
        super().__init__()
        self._executor = executor

    def generate_sequences(
        self,
    ) -> Tuple[tsc.TestSuiteChromosome, tsc.TestSuiteChromosome]:
        population: List[tsc.TestSuiteChromosome] = self._generate_random_population()
        return population[0], tsc.TestSuiteChromosome()

    def _generate_random_population(self) -> List[tsc.TestSuiteChromosome]:
        population = []
        for _ in range(config.INSTANCE.population):
            population.append(self._generate_random_suite())
        return population

    def _generate_random_suite(self) -> tsc.TestSuiteChromosome:
        new_suite = tsc.TestSuiteChromosome()
        num_tests = randomness.next_int(
            config.INSTANCE.min_initial_tests, config.INSTANCE.max_initial_tests + 1
        )

        for _ in range(num_tests):
            new_suite.add_test(self._generate_random_test_case())

        return new_suite

    # pylint: disable=no-self-use
    def _generate_random_test_case(self) -> tc.TestCase:
        test_case = dtc.DefaultTestCase()

        length = randomness.next_int(1, config.INSTANCE.chromosome_length)
        for _ in range(length):
            pass

        return test_case
