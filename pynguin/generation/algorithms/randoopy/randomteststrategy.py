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
"""Provides a random test generation algorithm similar to Randoop."""
import logging
from typing import List, Tuple, Set

import pynguin.configuration as config
import pynguin.ga.fitnessfunction as ff
import pynguin.testcase.defaulttestcase as dtc
import pynguin.testcase.testcase as tc
import pynguin.testsuite.testsuitechromosome as tsc
import pynguin.utils.generic.genericaccessibleobject as gao
from pynguin.generation.algorithms.testgenerationstrategy import TestGenerationStrategy
from pynguin.setup.testcluster import TestCluster
from pynguin.setup.testclustergenerator import TestClusterGenerator
from pynguin.testcase import testfactory
from pynguin.testcase.execution.abstractexecutor import AbstractExecutor
from pynguin.testcase.execution.executionresult import ExecutionResult
from pynguin.utils import randomness
from pynguin.utils.exceptions import GenerationException, ConstructionFailedException
from pynguin.utils.statistics.statistics import StatisticsTracker, RuntimeVariable
from pynguin.utils.statistics.timer import Timer


# pylint: disable=too-few-public-methods
class RandomTestStrategy(TestGenerationStrategy):
    """Implements a random test generation algorithm similar to Randoop."""

    _logger = logging.getLogger(__name__)

    def __init__(self, executor: AbstractExecutor) -> None:
        super(RandomTestStrategy, self).__init__()
        self._executor = executor
        self._execution_results: List[ExecutionResult] = []

    def generate_sequences(
        self,
    ) -> Tuple[tsc.TestSuiteChromosome, tsc.TestSuiteChromosome]:
        self._logger.info("Start generating sequences using random algorithm")
        timer = Timer(name="Sequences generation time", logger=None)
        timer.start()
        self._logger.debug("Time limit: %d", config.INSTANCE.budget)
        self._logger.debug("Module: %s", config.INSTANCE.module_name)
        StatisticsTracker().track_output_variable(
            RuntimeVariable.TARGET_CLASS, config.INSTANCE.module_name
        )

        test_chromosome: tsc.TestSuiteChromosome = tsc.TestSuiteChromosome()
        failing_test_chromosome: tsc.TestSuiteChromosome = tsc.TestSuiteChromosome()
        execution_counter: int = 0
        stopping_condition = self.get_stopping_condition()
        stopping_condition.reset()
        fitness_functions = self.get_fitness_functions()
        for fitness_function in fitness_functions:
            test_chromosome.add_fitness(fitness_function)
            failing_test_chromosome.add_fitness(fitness_function)

        with Timer(name="Test-cluster generation time", logger=None):
            test_cluster_generator = TestClusterGenerator(config.INSTANCE.module_name)
            test_cluster = test_cluster_generator.generate_cluster()

        while not self.is_fulfilled(stopping_condition):
            try:
                execution_counter += 1
                self.generate_sequence(
                    test_chromosome,
                    failing_test_chromosome,
                    test_cluster,
                    fitness_functions,
                    execution_counter,
                )
            except (ConstructionFailedException, GenerationException) as exception:
                self._logger.debug(
                    "Generate test case failed with exception %s", exception
                )

        self._logger.info("Finish generating sequences with random algorithm")
        timer.stop()
        self._logger.debug("Generated %d passing test cases", test_chromosome.size)
        self._logger.debug(
            "Generated %d failing test cases", failing_test_chromosome.size
        )
        self._logger.debug("Number of algorithm iterations: %d", execution_counter)

        return test_chromosome, failing_test_chromosome

    # pylint: disable=too-many-arguments
    def generate_sequence(
        self,
        test_chromosome: tsc.TestSuiteChromosome,
        failing_test_chromosome: tsc.TestSuiteChromosome,
        test_cluster: TestCluster,
        fitness_functions: List[ff.FitnessFunction],
        execution_counter: int,
    ) -> None:
        """Implements one step of the adapted Randoop algorithm.

        :param test_chromosome: The list of currently successful test cases
        :param failing_test_chromosome: The list of currently not successful test cases
        :param test_cluster: A cluster storing the available types and methods for
        test generation
        :param fitness_functions:
        :param execution_counter: A current number of algorithm iterations
        """
        self._logger.info("Algorithm iteration %d", execution_counter)
        timer = Timer(name="Sequence generation", logger=None)
        timer.start()
        objects_under_test: Set[
            gao.GenericAccessibleObject
        ] = test_cluster.accessible_objects_under_test

        if not objects_under_test:
            # In case we do not have any objects under test, we cannot generate a
            # test case.
            raise GenerationException(
                "Cannot generate test case without an object-under-test!"
            )

        clone = test_chromosome.clone()

        # Create new test case, i.e., sequence in Randoop paper terminology
        # Pick a random public method from objects under test
        method = self._random_public_method(objects_under_test)
        # Select random test cases from existing ones to base generation on
        tests = self._random_test_cases(clone.test_chromosomes)
        new_test: tc.TestCase = dtc.DefaultTestCase()
        for test in tests:
            new_test.append_test_case(test)

        # Generate random values as input for the previously picked random method
        # Extend the test case by the new method call
        testfactory.append_generic_statement(new_test, method)

        # Discard duplicates
        if (
            new_test in test_chromosome.test_chromosomes
            or new_test in failing_test_chromosome.test_chromosomes
        ):
            return

        with Timer(name="Execution time", logger=None):
            # Execute new sequence
            exec_result = self._executor.execute(new_test)

        # Classify new test case and outputs
        if exec_result.has_test_exceptions():
            failing_test_chromosome.add_test(new_test)
            for fitness_function in fitness_functions:
                fitness_function.get_fitness(failing_test_chromosome, exec_result)
        else:
            test_chromosome = clone
            test_chromosome.add_test(new_test)
            for fitness_function in fitness_functions:
                fitness_function.get_fitness(test_chromosome, exec_result)
            # TODO(sl) What about extensible flags?
        self._execution_results.append(exec_result)
        timer.stop()

    def send_statistics(self):
        super().send_statistics()
        tracker = StatisticsTracker()
        tracker.track_output_variable(
            RuntimeVariable.execution_results, self._execution_results
        )

    @staticmethod
    def _random_public_method(
        objects_under_test: Set[gao.GenericAccessibleObject],
    ) -> gao.GenericCallableAccessibleObject:
        object_under_test = randomness.RNG.choice(
            [
                obj
                for obj in objects_under_test
                if isinstance(obj, gao.GenericCallableAccessibleObject)
            ]
        )
        return object_under_test

    def _random_test_cases(self, test_cases: List[tc.TestCase]) -> List[tc.TestCase]:
        if config.INSTANCE.max_sequence_length == 0:
            selectables = test_cases
        else:
            selectables = [
                test_case
                for test_case in test_cases
                if len(test_case.statements) < config.INSTANCE.max_sequence_length
            ]
        if config.INSTANCE.max_sequences_combined == 0:
            upper_bound = len(selectables)
        else:
            upper_bound = min(len(selectables), config.INSTANCE.max_sequences_combined)
        new_test_cases = randomness.RNG.sample(
            selectables, randomness.RNG.randint(0, upper_bound)
        )
        self._logger.debug(
            "Selected %d new test cases from %d available ones",
            len(new_test_cases),
            len(test_cases),
        )
        return new_test_cases
