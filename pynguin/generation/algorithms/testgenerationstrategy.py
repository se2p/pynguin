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
"""Provides an abstract base class for a test generation algorithm."""
from abc import ABCMeta, abstractmethod
from typing import List, Tuple

import pynguin.configuration as config
import pynguin.ga.fitnessfunction as ff
import pynguin.ga.fitnessfunctions.branchdistancesuitefitness as bdsf
import pynguin.testcase.testcase as tc
import pynguin.testcase.testfactory as tf
import pynguin.testsuite.testsuitechromosome as tsc
from pynguin.generation.stoppingconditions.maxiterationsstoppingcondition import (
    MaxIterationsStoppingCondition,
)
from pynguin.generation.stoppingconditions.maxtestsstoppingcondition import (
    MaxTestsStoppingCondition,
)
from pynguin.generation.stoppingconditions.maxtimestoppingcondition import (
    MaxTimeStoppingCondition,
)
from pynguin.generation.stoppingconditions.stoppingcondition import StoppingCondition
from pynguin.setup.testcluster import TestCluster
from pynguin.testcase.execution.testcaseexecutor import TestCaseExecutor


class TestGenerationStrategy(metaclass=ABCMeta):
    """Provides an abstract base class for a test generation algorithm."""

    def __init__(self, executor: TestCaseExecutor, test_cluster: TestCluster) -> None:
        """Initialises the test-generation strategy.

        Args:
            executor: The executor the execute the generated test cases
            test_cluster: A cluster storing the available types and methods for test
                generation
        """
        self._executor = executor
        self._test_cluster = test_cluster
        self._test_factory = tf.TestFactory(test_cluster)

    @property
    def test_cluster(self) -> TestCluster:
        """Provide the test cluster.

        Returns:
            The test cluster
        """
        return self._test_cluster

    @property
    def test_factory(self) -> tf.TestFactory:
        """Provide the test factory.

        Returns:
            The test factory
        """
        return self._test_factory

    @abstractmethod
    def generate_sequences(
        self,
    ) -> Tuple[tsc.TestSuiteChromosome, tsc.TestSuiteChromosome]:
        """Generates sequences for a given module until the time limit is reached.

        Returns:  # noqa: DAR202
            A two-tuple of lists; the former containing the successful test
            cases, the latter containing the failing test cases.
        """

    def send_statistics(self):
        """Sends statistics of the current strategy to tracker."""

    @staticmethod
    def has_type_violations(exceptions: List[Exception]) -> bool:
        """Returns whether or not a list of exceptions contains a type violation.

        A type violation is an exception that indicates such a violation, i.e.,
        `TypeError` or `Attribute` error.

        Args:
            exceptions: A list of exceptions

        Returns:
            Whether or not the list contains a type violations
        """
        for exception in exceptions:
            if isinstance(exception, (TypeError, AttributeError)):
                return True
        return False

    @staticmethod
    def purge_test_cases(
        test_cases: List[tc.TestCase],
    ) -> Tuple[List[tc.TestCase], List[tc.TestCase]]:
        """Purges a list of test cases and returns the purged and remaining.

        A test case is purged if it contains more statements than configured by the
        `counter_threshold` configuration parameter.  The result is a tuple of two
        lists of test cases.  The first contains those test cases whose number of
        statements exceeds the `counter_threshold` value, the second list contains
        the remaining test cases, whose number of statements does not exceed the
        `counter_threshold`.

        In case the `counter_threshold` value is `0`, not purging happens; the first
        list of the result tuple will be empty then, the second will be a list of all
        test cases.

        Args:
            test_cases: A list of test cases

        Returns:
            A tuple of two lists of test cases.  The first contains test cases
            that where purged, the second contains the remaining test cases
        """
        if config.INSTANCE.counter_threshold <= 0:
            return [], test_cases

        purged: List[tc.TestCase] = []
        remaining: List[tc.TestCase] = []
        for test_case in test_cases:
            if len(test_case.statements) > config.INSTANCE.counter_threshold:
                purged.append(test_case)
            else:
                remaining.append(test_case)
        return purged, remaining

    @staticmethod
    def get_stopping_condition() -> StoppingCondition:
        """Instantiates the stopping condition depending on the configuration settings

        Returns:
            A stopping condition
        """
        stopping_condition = config.INSTANCE.stopping_condition
        if stopping_condition == config.StoppingCondition.MAX_ITERATIONS:
            return MaxIterationsStoppingCondition()
        if stopping_condition == config.StoppingCondition.MAX_TESTS:
            return MaxTestsStoppingCondition()
        if stopping_condition == config.StoppingCondition.MAX_TIME:
            return MaxTimeStoppingCondition()
        return MaxTimeStoppingCondition()

    def get_fitness_functions(self) -> List[ff.FitnessFunction]:
        """Converts a criterion into a test suite fitness function.

        Returns:
            A list of fitness functions
        """
        return [bdsf.BranchDistanceSuiteFitnessFunction(self._executor)]

    @staticmethod
    def is_fulfilled(stopping_condition: StoppingCondition) -> bool:
        """Checks whether a stopping condition is fulfilled.

        Args:
            stopping_condition: The stopping condition

        Returns:
            Whether or not the stopping condition is fulfilled
        """
        return stopping_condition.is_fulfilled()
