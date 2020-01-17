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
from typing import Type, List, Tuple, Set

from pynguin import Configuration
from pynguin.generation.algorithms.algorithm import GenerationAlgorithm
import pynguin.testcase.testcase as tc
from pynguin.generation.executor import Executor
from pynguin.generation.symboltable import SymbolTable
from pynguin.utils.exceptions import GenerationException
from pynguin.utils.recorder import CoverageRecorder


# pylint: disable=too-few-public-methods
from pynguin.utils.utils import get_members_from_module


class RandomGenerationAlgorithm(GenerationAlgorithm):
    """Implements a random test generation algorithm similar to Randoop."""

    _logger = logging.getLogger(__name__)

    def __init__(
        self,
        recorder: CoverageRecorder,
        executor: Executor,
        configuration: Configuration,
        symbol_table: SymbolTable,
    ) -> None:
        super().__init__(configuration)
        self._recorder = recorder
        self._executor = executor
        self._configuration = configuration
        self._symbol_table = symbol_table

    def generate_sequences(
        self, time_limit: int, modules: List[Type]
    ) -> Tuple[List[tc.TestCase], List[tc.TestCase]]:
        self._logger.info("Start generating sequences using random algorithm")
        self._logger.debug("Time limit: %d", time_limit)
        self._logger.debug("Modules: %s", modules)

        test_cases: List[tc.TestCase] = []
        failing_test_cases: List[tc.TestCase] = []
        archive: Set[tc.TestCase] = set()
        start_time = datetime.datetime.now()
        execution_counter: int = 0

        objects_under_test = self._find_objects_under_test(modules)

        while (datetime.datetime.now() - start_time).total_seconds() < time_limit:
            try:
                execution_counter += 1
                self._generate_sequence(
                    test_cases, failing_test_cases, archive, objects_under_test,
                )
            except GenerationException as exception:
                self._logger.debug(
                    "Generate test case failed with exception %s", exception
                )

        self._logger.info("Finish generating sequences with random algorithm")
        self._logger.debug("Generated %d passing test cases", len(test_cases))
        self._logger.debug("Generated %d failing test cases", len(failing_test_cases))
        self._logger.debug("Archive size: %d", len(archive))
        self._logger.debug("Number of algorithm iterations: %d", execution_counter)

        failing_test_cases = failing_test_cases + list(archive)
        return test_cases, failing_test_cases

    def _generate_sequence(
        self,
        test_cases: List[tc.TestCase],
        failing_test_cases: List[tc.TestCase],
        archive: Set[tc.TestCase],
        objects_under_test: List[Type],
    ) -> None:
        pass

    @staticmethod
    def _find_objects_under_test(types: List[Type]) -> List[Type]:
        objects_under_test = types.copy()
        for module in types:
            members = get_members_from_module(module)
            # members is tuple (name, module/class/function/method)
            objects_under_test = objects_under_test + [x[1] for x in members]
        return objects_under_test
