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
"""A random test generation strategy that utilises MonkeyType after the generation."""
import logging
from typing import List, Optional, Tuple

import pynguin.configuration as config
import pynguin.testsuite.testsuitechromosome as tsc
from pynguin.generation.algorithms.randoopy.monkeytypehandlermixin import (
    MonkeyTypeHandlerMixin,
)
from pynguin.generation.algorithms.randoopy.randomteststrategy import RandomTestStrategy
from pynguin.setup.testcluster import TestCluster
from pynguin.testcase.execution.monkeytypeexecutor import MonkeyTypeExecutor
from pynguin.testcase.execution.testcaseexecutor import TestCaseExecutor
from pynguin.utils.statistics.statistics import RuntimeVariable, StatisticsTracker


class RandomTestMonkeyTypeStrategy(RandomTestStrategy, MonkeyTypeHandlerMixin):
    """A random test generation strategy that utilises MonkeyType.

    The strategy does random test generation with an algorithm similar to Randoop.
    For a successfully generated test case the algorithm calls the MonkeyType tool
    and executes the test case under MonkeyType's supervision to gain type
    information.  The collected type information will be propagated back to the
    underlying `TestCluster`, such that it is available for the next algorithm
    iteration.
    """

    _logger = logging.getLogger(__name__)

    def __init__(self, executor: TestCaseExecutor, test_cluster: TestCluster) -> None:
        super().__init__(executor, test_cluster)
        self._monkey_type_executor = MonkeyTypeExecutor()
        self._monkey_type_executions = 0
        self._parameter_updates: List[
            Tuple[str, str, Optional[type], Optional[type]]
        ] = []
        self._return_type_updates: List[Tuple[str, Optional[type], Optional[type]]] = []

    def generate_sequence(
        self,
        test_chromosome: tsc.TestSuiteChromosome,
        failing_test_chromosome: tsc.TestSuiteChromosome,
        execution_counter: int,
    ) -> None:
        number_of_test_cases = test_chromosome.size()
        super().generate_sequence(
            test_chromosome, failing_test_chromosome, execution_counter,
        )
        self._call_monkey_type(number_of_test_cases, execution_counter, test_chromosome)

    def send_statistics(self):
        super().send_statistics()
        tracker = StatisticsTracker()
        tracker.track_output_variable(
            RuntimeVariable.MonkeyTypeExecutions, self._monkey_type_executions
        )
        tracker.track_output_variable(
            RuntimeVariable.ParameterTypeUpdates,
            [self._special_chars(str(p)) for p in self._parameter_updates],
        )
        tracker.track_output_variable(
            RuntimeVariable.ParameterTypeUpdatesSize, len(self._parameter_updates)
        )
        tracker.track_output_variable(
            RuntimeVariable.ReturnTypeUpdates,
            [self._special_chars(str(r)) for r in self._return_type_updates],
        )
        tracker.track_output_variable(
            RuntimeVariable.ReturnTypeUpdatesSize, len(self._return_type_updates)
        )

    @staticmethod
    def _special_chars(text: str) -> str:
        return (
            text.replace("&", "&amp;")
            .replace('"', "&quot;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

    def _call_monkey_type(
        self,
        number_of_test_cases: int,
        execution_counter: int,
        test_chromosome: tsc.TestSuiteChromosome,
    ) -> None:
        if execution_counter % config.INSTANCE.monkey_type_execution == 0:
            if test_chromosome.size() - number_of_test_cases == 1:
                self._logger.debug("Execute MonkeyType on single test case")
                self.execute_test_case_monkey_type(
                    [test_chromosome.test_chromosomes[-1]], self.test_cluster
                )
            elif test_chromosome.size() > number_of_test_cases:
                self._logger.debug("Execute MonkeyType on test suite")
                # TODO(sl) execute the full test suite or just the newly added test
                #  cases?
                self.execute_test_case_monkey_type(
                    test_chromosome.test_chromosomes, self.test_cluster
                )
