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
"""Provides a factories for generating different kind of test cases."""

from abc import abstractmethod

import pynguin.configuration as config
import pynguin.testcase.defaulttestcase as dtc
import pynguin.testcase.testcase as tc
import pynguin.testcase.testfactory as tf
from pynguin.utils import randomness


# pylint:disable=too-few-public-methods
class TestCaseFactory:
    """Abstract class for test case factories."""

    def __init__(self, test_factory: tf.TestFactory):
        """Instantiates the factory.

        Args:
            test_factory: The used test factory
        """
        self._test_factory = test_factory

    @abstractmethod
    def get_test_case(self) -> tc.TestCase:
        """Create a new random test case.

        Returns:
            A new random test case  # noqa: DAR202
        """


class RandomLengthTestCaseFactory(TestCaseFactory):
    """Create random test cases with random length."""

    def get_test_case(self) -> tc.TestCase:
        test_case = dtc.DefaultTestCase(self._test_factory)
        attempts = 0
        size = randomness.next_int(1, config.INSTANCE.chromosome_length + 1)

        while test_case.size() < size and attempts < config.INSTANCE.max_attempts:
            self._test_factory.insert_random_statement(test_case, test_case.size())
            attempts += 1
        return test_case
