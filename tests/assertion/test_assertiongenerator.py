#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
from unittest import mock
from unittest.mock import MagicMock

import pytest

import pynguin.assertion.assertiongenerator as ag
import pynguin.configuration as config


def test_init():
    executor = MagicMock()
    ag.AssertionGenerator(executor)
    assert executor.add_observer.call_count == 1


@pytest.fixture()
def generator_setup():
    executor = MagicMock()
    trace = MagicMock()
    assertion = MagicMock()
    trace.get_assertions.return_value = {assertion}
    result = MagicMock(assertion_traces={"": trace})
    executor.execute.return_value = result
    test_case = MagicMock()
    statement = MagicMock()
    test_case.statements = [statement]
    return test_case, executor, statement, assertion


def test__generate_assertions_short(generator_setup):
    test_case, executor, statement, assertion = generator_setup
    test_case.size_with_assertions.return_value = 1
    config.configuration.test_case_output.max_length_test_case = 2

    generator = ag.AssertionGenerator(executor)
    generator._generate_assertions([test_case])
    statement.add_assertion.assert_called_with(assertion)


def test__generate_assertions_long(generator_setup):
    test_case, executor, statement, _ = generator_setup
    test_case.size_with_assertions.return_value = 3
    config.configuration.test_case_output.max_length_test_case = 2

    generator = ag.AssertionGenerator(executor)
    generator._generate_assertions([test_case])
    statement.add_assertion.assert_not_called()


def test_filter_contradicting_assertions(generator_setup):
    executor = MagicMock()
    trace = MagicMock()
    assertion = MagicMock()
    assertion_2 = MagicMock()
    trace.get_assertions.side_effect = [{assertion}, {assertion_2}]
    result = MagicMock(assertion_traces={"": trace})
    executor.execute.return_value = result
    test_case = MagicMock()
    statement = MagicMock()
    test_case.statements = [statement]

    test_case.size_with_assertions.return_value = 1
    config.configuration.test_case_output.max_length_test_case = 2

    generator = ag.AssertionGenerator(executor)
    generator._generate_assertions([test_case])
    statement.add_assertion.assert_not_called()


def test_visit_suite():
    executor = MagicMock()
    gen = ag.AssertionGenerator(executor)
    test = MagicMock(test_case=MagicMock())
    suite = MagicMock(test_case_chromosomes=[test])
    with mock.patch.object(gen, "_generate_assertions") as gen_mock:
        gen.visit_test_suite_chromosome(suite)
        gen_mock.assert_called_with([test.test_case])


def test_visit_test():
    executor = MagicMock()
    gen = ag.AssertionGenerator(executor)
    test = MagicMock(test_case=MagicMock())
    with mock.patch.object(gen, "_generate_assertions") as gen_mock:
        gen.visit_test_case_chromosome(test)
        gen_mock.assert_called_with([test.test_case])
