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
import pynguin.testcase.defaulttestcase as dtc
import pynguin.testcase.testcase as tc
import pynguin.utils.generic.genericaccessibleobject as gao
from pynguin.generation.algorithms.testgenerationstrategy import TestGenerationStrategy
from pynguin.setup.testcluster import TestCluster
from pynguin.setup.testclustergenerator import TestClusterGenerator
from pynguin.testcase import testfactory
from pynguin.testcase.execution.testcaseexecutor import TestCaseExecutor
from pynguin.utils import randomness
from pynguin.utils.exceptions import GenerationException


# pylint: disable=too-few-public-methods
class RandomTestStrategy(TestGenerationStrategy):
    """Implements a random test generation algorithm similar to Randoop."""

    _logger = logging.getLogger(__name__)

    def __init__(self, executor: TestCaseExecutor,) -> None:
        super().__init__()
        self._executor = executor

    def generate_sequences(self) -> Tuple[List[tc.TestCase], List[tc.TestCase]]:
        self._logger.info("Start generating sequences using random algorithm")
        self._logger.debug("Time limit: %d", config.INSTANCE.budget)
        self._logger.debug("Module: %s", config.INSTANCE.module_name)

        test_cases: List[tc.TestCase] = []
        failing_test_cases: List[tc.TestCase] = []
        execution_counter: int = 0
        stopping_condition = self.get_stopping_condition()
        stopping_condition.reset()

        test_cluster_generator = TestClusterGenerator(config.INSTANCE.module_name)
        test_cluster = test_cluster_generator.generate_cluster()

        while not self.is_fulfilled(stopping_condition):
            try:
                execution_counter += 1
                self._generate_sequence(
                    test_cases, failing_test_cases, test_cluster,
                )
            except GenerationException as exception:
                self._logger.debug(
                    "Generate test case failed with exception %s", exception
                )

        self._logger.info("Finish generating sequences with random algorithm")
        self._logger.debug("Generated %d passing test cases", len(test_cases))
        self._logger.debug("Generated %d failing test cases", len(failing_test_cases))
        self._logger.debug("Number of algorithm iterations: %d", execution_counter)

        return test_cases, failing_test_cases

    def _generate_sequence(
        self,
        test_cases: List[tc.TestCase],
        failing_test_cases: List[tc.TestCase],
        test_cluster: TestCluster,
    ) -> None:
        """Implements one step of the adapted Randoop algorithm.

        :param test_cases: The list of currently successful test cases
        :param failing_test_cases: The list of currently not successful test cases
        :param test_cluster: A cluster storing the available types and methods for
        test generation
        """
        objects_under_test: Set[
            gao.GenericAccessibleObject
        ] = test_cluster.accessible_objects_under_test

        # Create new test case, i.e., sequence in Randoop paper terminology
        # Pick a random public method from objects under test
        method = self._random_public_method(objects_under_test)
        # Select random test cases from existing ones to base generation on
        tests = self._random_test_cases(test_cases)
        new_test: tc.TestCase = dtc.DefaultTestCase()
        for test in tests:
            new_test.append_test_case(test)

        # Generate random values as input for the previously picked random method
        # Extend the test case by the new method call
        testfactory.append_generic_statement(new_test, method)

        # Discard duplicates
        if new_test in test_cases or new_test in failing_test_cases:
            return

        # Execute new sequence
        exec_result = self._executor.execute(new_test)

        # Classify new test case and outputs
        if exec_result.has_test_exceptions():
            failing_test_cases.append(new_test)
        else:
            test_cases.append(new_test)
            # TODO(sl) What about extensible flags?

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
