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
from typing import Tuple, List, Type

import pynguin.testcase.testcase as tc
import pynguin.configuration as config


class GenerationAlgorithm(metaclass=ABCMeta):
    """Provides an abstract base class for a test generation algorithm."""

    def __init__(self) -> None:
        pass

    @abstractmethod
    def generate_sequences(
        self, time_limit: int, modules: List[Type]
    ) -> Tuple[List[tc.TestCase], List[tc.TestCase]]:
        """Generates sequences for a given module until the time limit is reached.

        :param time_limit: The maximum amount of time that shall be consumed
        :param modules: The list of types that are available
        :return: A two-tuple of lists; the former containing the successful test
        cases, the latter containing the failing test cases.
        """

    @staticmethod
    def has_type_violations(exceptions: List[Exception]) -> bool:
        """Returns whether or not a list of exceptions contains a type violation.

        A type violation is an exception that indicates such a violation, i.e.,
        `TypeError` or `Attribute` error.

        :param exceptions: A list of exceptions
        :return: Whether or not the list contains a type violations
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

        :param test_cases: A list of test cases
        :return: A tuple of two lists of test cases.  The first contains test cases
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
