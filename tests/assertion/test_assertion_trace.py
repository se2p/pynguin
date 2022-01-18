#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
from unittest.mock import MagicMock

import pytest
from ordered_set import OrderedSet

import pynguin.assertion.assertion_trace as at


@pytest.fixture
def assertion_trace():
    return at.AssertionTrace()


def test_empty(assertion_trace):
    assert assertion_trace._trace == {}


def test_add_entry(assertion_trace):
    variable = MagicMock()
    variable.get_statement_position.return_value = 42
    entry = MagicMock()
    assertion_trace.add_entry(1337, entry)
    assert assertion_trace._trace == {1337: {entry}}


def test_add_entry_same_position(assertion_trace):
    entry = MagicMock()
    assertion_trace.add_entry(1337, entry)
    assertion_trace.add_entry(1337, entry)
    assert assertion_trace._trace == {1337: {entry}}


def test_clear(assertion_trace):
    entry = MagicMock()
    assertion_trace.add_entry(1337, entry)
    assertion_trace.clear()
    assert assertion_trace._trace == {}


def test_clone(assertion_trace):
    entry = MagicMock()
    assertion_trace.add_entry(1337, entry)
    clone = assertion_trace.clone()
    assert dict(clone._trace) == {1337: OrderedSet([entry])}
    assert assertion_trace._trace is not clone._trace


def test_get_assertions_empty(assertion_trace):
    statement = MagicMock()
    statement.get_position.return_value = 3
    assert assertion_trace.get_assertions(statement) == set()


def test_get_assertions(assertion_trace):
    entry = MagicMock()
    assertion_trace.add_entry(3, entry)
    statement = MagicMock()
    statement.get_position.return_value = 3
    assert assertion_trace.get_assertions(statement) == {entry}
