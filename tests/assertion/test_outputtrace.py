#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
from unittest.mock import MagicMock

import pytest

import pynguin.assertion.outputtrace as ot
import pynguin.configuration as config


def test_empty():
    trace = ot.OutputTrace()
    assert trace._trace == {}


def test_add_entry():
    trace = ot.OutputTrace()
    variable = MagicMock()
    variable.get_statement_position.return_value = 42
    entry = MagicMock()
    trace.add_entry(1337, variable, entry)
    assert trace._trace == {1337: {42: entry}}


def test_add_entry_same_position():
    trace = ot.OutputTrace()
    variable = MagicMock()
    variable.get_statement_position.return_value = 42
    entry = MagicMock()
    trace.add_entry(1337, variable, entry)
    trace.add_entry(1337, variable, entry)
    assert trace._trace == {1337: {42: entry}}


@pytest.fixture
def sample_trace_assertion():
    trace = ot.OutputTrace()
    variable = MagicMock()
    variable.get_statement_position.return_value = 42
    entry = MagicMock()
    assertion = MagicMock()
    entry.get_assertions.return_value = ({assertion})
    trace.add_entry(1337, variable, entry)
    return trace, assertion


def test_add_assertions_test_case_to_long(sample_trace_assertion):
    trace, assertion = sample_trace_assertion

    test_case = MagicMock()
    test_case.size_with_assertions.return_value = 7
    config.INSTANCE.max_length_test_case = 7

    trace.add_assertions(test_case)
    test_case.get_statement.assert_not_called()


def test_add_assertions_test_case_small(sample_trace_assertion):
    trace, assertion = sample_trace_assertion

    test_case = MagicMock()
    statement = MagicMock()
    test_case.get_statement.return_value = statement
    test_case.size_with_assertions.return_value = 6
    config.INSTANCE.max_length_test_case = 7

    trace.add_assertions(test_case)
    test_case.get_statement.assert_called_with(1337)
    statement.add_assertion.assert_called_with(assertion)


def test_clear():
    trace = ot.OutputTrace()
    variable = MagicMock()
    variable.get_statement_position.return_value = 42
    entry = MagicMock()
    trace.add_entry(1337, variable, entry)
    trace.clear()
    assert trace._trace == {}


def test_clone():
    trace = ot.OutputTrace()
    variable = MagicMock()
    variable.get_statement_position.return_value = 42
    entry = MagicMock()
    cloned_entry = MagicMock()
    entry.clone.return_value = cloned_entry
    trace.add_entry(1337, variable, entry)
    clone = trace.clone()
    assert clone._trace == {1337: {42: cloned_entry}}
