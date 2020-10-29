#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
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
    assert executor.add_observer.call_count == 2


def test_add_assertions():
    executor = MagicMock()
    generator = ag.AssertionGenerator(executor)
    test_case = MagicMock()
    with mock.patch.object(generator, "_add_assertions") as add:
        generator.add_assertions([test_case])
        add.assert_called_with(test_case)


@pytest.fixture()
def generator_setup():
    executor = MagicMock()
    trace = MagicMock()
    assertion = MagicMock()
    trace.get_assertions.return_value = {assertion}
    result = MagicMock(output_traces={"": trace})
    executor.execute.return_value = result
    test_case = MagicMock()
    statement = MagicMock()
    test_case.statements = [statement]
    return test_case, executor, statement, assertion


def test__add_assertions_short(generator_setup):
    test_case, executor, statement, assertion = generator_setup
    test_case.size_with_assertions.return_value = 1
    config.INSTANCE.max_length_test_case = 2

    generator = ag.AssertionGenerator(executor)
    generator._add_assertions(test_case)
    statement.add_assertion.assert_called_with(assertion)


def test__add_assertions_long(generator_setup):
    test_case, executor, statement, _ = generator_setup
    test_case.size_with_assertions.return_value = 3
    config.INSTANCE.max_length_test_case = 2

    generator = ag.AssertionGenerator(executor)
    generator._add_assertions(test_case)
    statement.add_assertion.assert_not_called()


def test__filter_failing_assertions(generator_setup):
    test_case, executor, statement, _ = generator_setup

    statement.assertions = {MagicMock}
    generator = ag.AssertionGenerator(executor)
    generator._filter_failing_assertions(test_case)
    assert statement.assertions == set()


def test_filter_assertions():
    executor = MagicMock()
    generator = ag.AssertionGenerator(executor)
    test_case = MagicMock()
    with mock.patch.object(generator, "_filter_failing_assertions") as filt:
        generator.filter_failing_assertions([test_case])
        filt.assert_called_with(test_case)
