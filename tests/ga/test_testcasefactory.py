#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
from unittest.mock import MagicMock

import pynguin.configuration as config
import pynguin.ga.testcasefactory as tcf
import pynguin.testcase.testfactory as tf


def test_get_test_case_max_attempts():
    test_factory = MagicMock(tf.TestFactory)
    test_case_factory = tcf.RandomLengthTestCaseFactory(test_factory, MagicMock())
    test_case_factory.get_test_case()
    assert (
        test_factory.insert_random_statement.call_count
        == config.configuration.test_creation.max_attempts
    )


def test_get_test_case_success():
    test_factory = MagicMock(tf.TestFactory)
    test_factory.insert_random_statement.side_effect = (
        lambda test_case, _pos: test_case.add_statement(MagicMock(), 0)
    )
    test_case_factory = tcf.RandomLengthTestCaseFactory(test_factory, MagicMock())
    test_case_factory.get_test_case()
    assert (
        1
        <= test_factory.insert_random_statement.call_count
        <= config.configuration.search_algorithm.chromosome_length
    )
