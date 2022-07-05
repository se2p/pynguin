#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
from unittest import mock
from unittest.mock import MagicMock

import pytest

import pynguin.assertion.assertiongenerator as ag
import pynguin.configuration as config


@pytest.fixture()
def generator_setup():
    test_case = MagicMock()
    statement = MagicMock()
    test_case.statements = [statement]
    return test_case, statement


def test__generate_assertions_short(generator_setup):
    test_case, statement = generator_setup
    test_case.size_with_assertions.return_value = 1
    config.configuration.test_case_output.max_length_test_case = 2

    trace = MagicMock()
    assertion = MagicMock()
    trace.get_assertions.return_value = {assertion}
    result = MagicMock(assertion_traces={"": trace})

    executor = MagicMock()
    executor.execute.return_value = result

    generator = ag.AssertionGenerator(executor)
    with mock.patch.object(generator, "_mutation_executor") as executor_mock:
        executor_mock.execute.return_value = result
        generator._generate_assertions([test_case])
        statement.add_assertion.assert_called_with(assertion)


def test__generate_assertions_long(generator_setup):
    test_case, statement = generator_setup
    test_case.size_with_assertions.return_value = 3
    config.configuration.test_case_output.max_length_test_case = 2

    trace = MagicMock()
    assertion = MagicMock()
    trace.get_assertions.return_value = {assertion}
    result = MagicMock(assertion_traces={"": trace})

    executor = MagicMock()
    executor.execute.return_value = result

    generator = ag.AssertionGenerator(executor)
    with mock.patch.object(generator, "_mutation_executor") as executor_mock:
        executor_mock.execute.return_value = result
        generator._generate_assertions([test_case])
        statement.add_assertion.assert_not_called()


def test_filter_contradicting_assertions(generator_setup):
    trace = MagicMock()
    assertion = MagicMock()
    assertion_2 = MagicMock()
    trace.get_assertions.side_effect = [{assertion}, {assertion_2}]
    result = MagicMock(assertion_traces={"": trace})

    executor = MagicMock()
    executor.execute.return_value = result

    generator = ag.AssertionGenerator(executor)
    with mock.patch.object(generator, "_mutation_executor") as executor_mock:
        executor_mock.execute.return_value = result
        test_case = MagicMock()
        statement = MagicMock()
        test_case.statements = [statement]

        test_case.size_with_assertions.return_value = 1
        config.configuration.test_case_output.max_length_test_case = 2

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
