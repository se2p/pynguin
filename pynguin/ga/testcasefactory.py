#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides a factories for generating different kind of test cases."""

from abc import abstractmethod

import pynguin.configuration as config
import pynguin.testcase.defaulttestcase as dtc
import pynguin.testcase.testcase as tc
import pynguin.testcase.testfactory as tf
from pynguin.analyses.seeding.initialpopulationseeding import InitialPopulationSeeding
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
        if (
            config.INSTANCE.initial_population_seeding
            and InitialPopulationSeeding().has_tests
            and randomness.next_float() <= 0.90
        ):
            test_case = InitialPopulationSeeding().random_testcase
        else:
            test_case = dtc.DefaultTestCase()
            attempts = 0
            size = randomness.next_int(1, config.INSTANCE.chromosome_length + 1)

            while test_case.size() < size and attempts < config.INSTANCE.max_attempts:
                self._test_factory.insert_random_statement(test_case, test_case.size())
                attempts += 1
        return test_case
