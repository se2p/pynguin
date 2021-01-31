#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides a factories for generating different kind of test cases."""

from abc import abstractmethod

import pynguin.configuration as config
import pynguin.testcase.defaulttestcase as dtc
import pynguin.testcase.testcase as tc
import pynguin.testcase.testfactory as tf
import pynguin.analyses.seeding.initialpopulationseeding as initpopseeding
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
        """Retrieve a test case.

        Returns:
            A test case  # noqa: DAR202
        """


class RandomLengthTestCaseFactory(TestCaseFactory):
    """Create random test cases with random length."""

    def get_test_case(self) -> tc.TestCase:
        test_case = dtc.DefaultTestCase()
        attempts = 0
        size = randomness.next_int(1, config.configuration.chromosome_length + 1)

        while test_case.size() < size and attempts < config.configuration.max_attempts:
            self._test_factory.insert_random_statement(test_case, test_case.size())
            attempts += 1
        return test_case


class SeededTestCaseFactory(TestCaseFactory):
    """Factory for getting seeded test cases. With a certain probability a seeded testcase is returned instead of a
    randomly generated one. If a seeded testcase is returned, it is taken randomly from the pool of seeded testcases.
    If a randomly generated testcase is returned, the generation is delegated to the RandomLengthTestCaseFactory."""

    def __init__(self, delegate: TestCaseFactory, test_factory: tf.TestFactory):
        super().__init__(test_factory)
        self._delegate = delegate

    def get_test_case(self) -> tc.TestCase:
        if (
            config.configuration.initial_population_seeding
            and initpopseeding.initialpopulationseeding.has_tests
            and randomness.next_float() <= 0.90
        ):
            return initpopseeding.initialpopulationseeding.seeded_testcase
        else:
            return self._delegate.get_test_case()
