#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
from unittest.mock import MagicMock

import pytest

import pynguin.assertion.assertion_trace as at

from pynguin.utils.orderedset import OrderedSet


@pytest.fixture
def assertion_trace():
    return at.AssertionTrace()


def test_empty(assertion_trace):
    assert assertion_trace.trace == {}


def test_add_entry(assertion_trace):
    variable = MagicMock()
    variable.get_statement_position.return_value = 42
    entry = MagicMock()
    assertion_trace.add_entry(1337, entry)
    assert assertion_trace.trace == {1337: OrderedSet([entry])}


def test_add_entry_same_position(assertion_trace):
    entry = MagicMock()
    assertion_trace.add_entry(1337, entry)
    assertion_trace.add_entry(1337, entry)
    assert assertion_trace.trace == {1337: OrderedSet([entry])}


def test_clear(assertion_trace):
    entry = MagicMock()
    assertion_trace.add_entry(1337, entry)
    assertion_trace.clear()
    assert assertion_trace.trace == {}


def test_clone(assertion_trace):
    entry = MagicMock()
    assertion_trace.add_entry(1337, entry)
    clone = assertion_trace.clone()
    assert dict(clone.trace) == {1337: OrderedSet([entry])}
    assert assertion_trace.trace is not clone.trace


def test_get_assertions_empty(assertion_trace):
    statement = MagicMock()
    statement.get_position.return_value = 3
    assert assertion_trace.get_assertions(statement) == OrderedSet()


def test_get_assertions(assertion_trace):
    entry = MagicMock()
    assertion_trace.add_entry(3, entry)
    statement = MagicMock()
    statement.get_position.return_value = 3
    assert assertion_trace.get_assertions(statement) == OrderedSet([entry])


def test_merge():
    ver_trace = at.AssertionVerificationTrace()
    assert not ver_trace.was_violated(0, 0)


def test_merge_2():
    ver_trace = at.AssertionVerificationTrace()
    ver_trace.error[0].add(0)
    assert ver_trace.was_violated(0, 0)


def test_merge_3():
    ver_trace = at.AssertionVerificationTrace()
    ver_trace.failed[0].add(0)
    assert ver_trace.was_violated(0, 0)
