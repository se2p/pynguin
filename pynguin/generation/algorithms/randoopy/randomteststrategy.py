#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides a random test generation algorithm similar to Randoop."""
import logging
from typing import List, Set

import pynguin.configuration as config
import pynguin.ga.testcasechromosome as tcc
import pynguin.ga.testsuitechromosome as tsc
import pynguin.testcase.defaulttestcase as dtc
import pynguin.testcase.testcase as tc
import pynguin.utils.generic.genericaccessibleobject as gao
from pynguin.generation.algorithms.testgenerationstrategy import TestGenerationStrategy
from pynguin.setup.testcluster import TestCluster
from pynguin.testcase.execution.executionresult import ExecutionResult
from pynguin.testcase.execution.testcaseexecutor import TestCaseExecutor
from pynguin.utils import randomness
from pynguin.utils.exceptions import ConstructionFailedException, GenerationException
from pynguin.utils.statistics.statistics import RuntimeVariable, StatisticsTracker
from pynguin.utils.statistics.timer import Timer


class RandomTestStrategy(TestGenerationStrategy):
    """Implements a random test generation algorithm similar to Randoop."""

    _logger = logging.getLogger(__name__)

    def __init__(self, executor: TestCaseExecutor, test_cluster: TestCluster) -> None:
        super().__init__(executor, test_cluster)
        self._execution_results: List[ExecutionResult] = []

    def generate_sequences(
        self,
    ) -> tsc.TestSuiteChromosome:
        stopping_condition = self.get_stopping_condition()
        stopping_condition.reset()
        test_chromosome: tsc.TestSuiteChromosome = tsc.TestSuiteChromosome()
        failing_test_chromosome: tsc.TestSuiteChromosome = tsc.TestSuiteChromosome()
        generation: int = 0
        fitness_functions = self.get_fitness_functions()
        for fitness_function in fitness_functions:
            test_chromosome.add_fitness_function(fitness_function)
            failing_test_chromosome.add_fitness_function(fitness_function)

        combined_chromosome = self._combine_current_individual(
            test_chromosome, failing_test_chromosome
        )

        while (
            not self.is_fulfilled(stopping_condition)
            and combined_chromosome.get_fitness() != 0.0
        ):
            try:
                generation += 1
                stopping_condition.iterate()
                self.generate_sequence(
                    test_chromosome,
                    failing_test_chromosome,
                    generation,
                )
                combined_chromosome = self._combine_current_individual(
                    test_chromosome, failing_test_chromosome
                )
                StatisticsTracker().current_individual(combined_chromosome)
                self._logger.info(
                    "Generation: %5i. Best fitness: %5f, Best coverage %5f",
                    generation,
                    combined_chromosome.get_fitness(),
                    combined_chromosome.get_coverage(),
                )
            except (ConstructionFailedException, GenerationException) as exception:
                self._logger.debug(
                    "Generate test case failed with exception %s", exception
                )

        self._logger.debug("Number of algorithm iterations: %d", generation)
        StatisticsTracker().track_output_variable(
            RuntimeVariable.AlgorithmIterations, generation
        )

        combined_chromosome = self._combine_current_individual(
            test_chromosome, failing_test_chromosome
        )
        return combined_chromosome

    def generate_sequence(
        self,
        test_chromosome: tsc.TestSuiteChromosome,
        failing_test_chromosome: tsc.TestSuiteChromosome,
        execution_counter: int,
    ) -> None:
        """Implements one step of the adapted Randoop algorithm.

        Args:
            test_chromosome: The list of currently successful test cases
            failing_test_chromosome: The list of currently not successful test cases
            execution_counter: A current number of algorithm iterations

        Raises:
            GenerationException: In case an error occurs during generation
        """
        self._logger.info("Algorithm iteration %d", execution_counter)
        timer = Timer(name="Sequence generation", logger=None)
        timer.start()
        objects_under_test: Set[
            gao.GenericAccessibleObject
        ] = self.test_cluster.accessible_objects_under_test

        if not objects_under_test:
            # In case we do not have any objects under test, we cannot generate a
            # test case.
            raise GenerationException(
                "Cannot generate test case without an object-under-test!"
            )

        # Create new test case, i.e., sequence in Randoop paper terminology
        # Pick a random public method from objects under test
        method = self._random_public_method(objects_under_test)
        # Select random test cases from existing ones to base generation on
        tests = self._random_test_cases(
            [
                chromosome.test_case
                for chromosome in test_chromosome.test_case_chromosomes
            ]
        )
        new_test = tcc.TestCaseChromosome(dtc.DefaultTestCase())
        for test in tests:
            new_test.test_case.append_test_case(test)

        # Generate random values as input for the previously picked random method
        # Extend the test case by the new method call
        self.test_factory.append_generic_accessible(new_test.test_case, method)

        # Discard duplicates
        if (
            new_test in test_chromosome.test_case_chromosomes
            or new_test in failing_test_chromosome.test_case_chromosomes
        ):
            return

        with Timer(name="Execution time", logger=None):
            # Execute new sequence
            exec_result = self._executor.execute(new_test.test_case)

        # Classify new test case and outputs
        if exec_result.has_test_exceptions():
            failing_test_chromosome.add_test_case_chromosome(new_test)
        else:
            test_chromosome.add_test_case_chromosome(new_test)
            # TODO(sl) What about extensible flags?
        self._execution_results.append(exec_result)
        timer.stop()

    @staticmethod
    def _combine_current_individual(
        passing_chromosome: tsc.TestSuiteChromosome,
        failing_chromosome: tsc.TestSuiteChromosome,
    ) -> tsc.TestSuiteChromosome:
        combined = passing_chromosome.clone()
        combined.add_test_case_chromosomes(failing_chromosome.test_case_chromosomes)
        return combined

    def send_statistics(self) -> None:
        super().send_statistics()
        tracker = StatisticsTracker()
        tracker.track_output_variable(
            RuntimeVariable.ExecutionResults, self._execution_results
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
