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
import datetime
import logging
import random
from typing import Type, List, Tuple

import pynguin.configuration as config
import pynguin.testcase.testcase as tc
from pynguin.generation.algorithms.testgenerationstrategy import TestGenerationStrategy
from pynguin.generation.symboltable import SymbolTable
from pynguin.testcase.execution.testcaseexecutor import TestCaseExecutor
from pynguin.typeinference.strategy import TypeInferenceStrategy
from pynguin.utils.exceptions import GenerationException
from pynguin.utils.recorder import CoverageRecorder


# pylint: disable=too-few-public-methods


class RandomTestStrategy(TestGenerationStrategy):
    """Implements a random test generation algorithm similar to Randoop."""

    _logger = logging.getLogger(__name__)

    # pylint: disable=too-many-arguments
    def __init__(
        self,
        recorder: CoverageRecorder,
        executor: TestCaseExecutor,
        symbol_table: SymbolTable,
        type_inference_strategy: TypeInferenceStrategy,
    ) -> None:
        super().__init__()
        self._recorder = recorder
        self._executor = executor
        self._symbol_table = symbol_table
        self._type_inference_strategy = type_inference_strategy

    def generate_sequences(
        self, time_limit: int, modules: List[Type]
    ) -> Tuple[List[tc.TestCase], List[tc.TestCase]]:
        self._logger.info("Start generating sequences using random algorithm")
        self._logger.debug("Time limit: %d", time_limit)
        self._logger.debug("Modules: %s", modules)

        test_cases: List[tc.TestCase] = []
        failing_test_cases: List[tc.TestCase] = []
        start_time = datetime.datetime.now()
        execution_counter: int = 0

        objects_under_test: List[Type] = []  # Select all objects under test

        while (datetime.datetime.now() - start_time).total_seconds() < time_limit:
            try:
                execution_counter += 1
                self._generate_sequence(
                    test_cases, failing_test_cases, objects_under_test,
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
        objects_under_test: List[Type],
    ) -> None:
        """Implements one step of the adapted Randoop algorithm.

        :param test_cases: The list of currently successful test cases
        :param failing_test_cases: The list of currently not successful test cases
        :param objects_under_test: The list of available types in the current context
        """
        # Create new test case, i.e., sequence in Randoop paper terminology
        # Pick a random public method from objects under test
        # Select random test cases from existing ones to base generation on
        # Generate random values as input for the previously picked random method
        # Extend the test case by the new method call

        # Discard duplicates

        # Execute new sequence

        # Classify new test case and outputs

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
        new_test_cases = random.sample(selectables, random.randint(0, upper_bound))
        self._logger.debug(
            "Selected %d new test cases from %d available ones",
            len(new_test_cases),
            len(test_cases),
        )
        return new_test_cases
