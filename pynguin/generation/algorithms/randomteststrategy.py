#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides a random test generation algorithm similar to Randoop."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ordered_set import OrderedSet

import pynguin.configuration as config
import pynguin.ga.testcasechromosome as tcc
import pynguin.ga.testsuitechromosome as tsc
import pynguin.testcase.defaulttestcase as dtc
import pynguin.utils.generic.genericaccessibleobject as gao
import pynguin.utils.statistics.statistics as stat
from pynguin.generation.algorithms.testgenerationstrategy import TestGenerationStrategy
from pynguin.utils import randomness
from pynguin.utils.exceptions import ConstructionFailedException, GenerationException
from pynguin.utils.statistics.runtimevariable import RuntimeVariable

if TYPE_CHECKING:
    import pynguin.testcase.testcase as tc
    from pynguin.testcase.execution import ExecutionResult


class RandomTestStrategy(TestGenerationStrategy):
    """Implements a random test generation algorithm similar to Randoop."""

    _logger = logging.getLogger(__name__)

    def __init__(self) -> None:
        super().__init__()
        self._execution_results: list[ExecutionResult] = []

    def generate_tests(
        self,
    ) -> tsc.TestSuiteChromosome:
        self.before_search_start()
        test_chromosome: tsc.TestSuiteChromosome = tsc.TestSuiteChromosome()
        failing_test_chromosome: tsc.TestSuiteChromosome = tsc.TestSuiteChromosome()
        for fitness_function in self._test_suite_fitness_functions:
            test_chromosome.add_fitness_function(fitness_function)
            failing_test_chromosome.add_fitness_function(fitness_function)

        for coverage_function in self._test_suite_coverage_functions:
            test_chromosome.add_coverage_function(coverage_function)
            failing_test_chromosome.add_coverage_function(coverage_function)

        combined_chromosome = self._combine_current_individual(
            test_chromosome, failing_test_chromosome
        )

        self.before_first_search_iteration(combined_chromosome)
        while self.resources_left() and combined_chromosome.get_fitness() != 0.0:
            try:
                self.generate_sequence(
                    test_chromosome,
                    failing_test_chromosome,
                )
                combined_chromosome = self._combine_current_individual(
                    test_chromosome, failing_test_chromosome
                )
            except (ConstructionFailedException, GenerationException) as exception:
                self._logger.debug(
                    "Generate test case failed with exception %s", exception
                )
            self.after_search_iteration(combined_chromosome)

        # TODO(fk) is this still required?
        stat.track_output_variable(
            RuntimeVariable.ExecutionResults, self._execution_results
        )
        self.after_search_finish()
        return combined_chromosome

    def generate_sequence(
        self,
        test_chromosome: tsc.TestSuiteChromosome,
        failing_test_chromosome: tsc.TestSuiteChromosome,
    ) -> None:
        """Implements one step of the adapted Randoop algorithm.

        Args:
            test_chromosome: The list of currently successful test cases
            failing_test_chromosome: The list of currently not successful test cases

        Raises:
            GenerationException: In case an error occurs during generation
        """
        objects_under_test: OrderedSet[
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

        # Execute new sequence
        exec_result = self._executor.execute(new_test.test_case)
        new_test.set_last_execution_result(exec_result)
        new_test.set_changed(False)

        # Classify new test case and outputs
        if exec_result.has_test_exceptions():
            failing_test_chromosome.add_test_case_chromosome(new_test)
        else:
            test_chromosome.add_test_case_chromosome(new_test)
            # TODO(sl) What about extensible flags?
        self._execution_results.append(exec_result)

    @staticmethod
    def _combine_current_individual(
        passing_chromosome: tsc.TestSuiteChromosome,
        failing_chromosome: tsc.TestSuiteChromosome,
    ) -> tsc.TestSuiteChromosome:
        combined = passing_chromosome.clone()
        combined.add_test_case_chromosomes(failing_chromosome.test_case_chromosomes)
        return combined

    @staticmethod
    def _random_public_method(
        objects_under_test: OrderedSet[gao.GenericAccessibleObject],
    ) -> gao.GenericCallableAccessibleObject:
        object_under_test = randomness.RNG.choice(
            [
                obj
                for obj in objects_under_test
                if isinstance(obj, gao.GenericCallableAccessibleObject)
            ]
        )
        return object_under_test

    def _random_test_cases(self, test_cases: list[tc.TestCase]) -> list[tc.TestCase]:
        if config.configuration.random.max_sequence_length == 0:
            selectables = test_cases
        else:
            selectables = [
                test_case
                for test_case in test_cases
                if len(test_case.statements)
                < config.configuration.random.max_sequence_length
            ]
        if config.configuration.random.max_sequences_combined == 0:
            upper_bound = len(selectables)
        else:
            upper_bound = min(
                len(selectables), config.configuration.random.max_sequences_combined
            )
        new_test_cases = randomness.RNG.sample(
            selectables, randomness.RNG.randint(0, upper_bound)
        )
        self._logger.debug(
            "Selected %d new test cases from %d available ones",
            len(new_test_cases),
            len(test_cases),
        )
        return new_test_cases
