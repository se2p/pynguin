#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
from unittest.mock import MagicMock

import pynguin.assertion.outputtrace as ot


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


def test_get_assertions_empty():
    statement = MagicMock()
    statement.get_position.return_value = 3
    trace = ot.OutputTrace()
    assert trace.get_assertions(statement) == set()


def test_get_assertions():
    trace = ot.OutputTrace()
    variable = MagicMock()
    variable.get_statement_position.return_value = 42
    entry = MagicMock()
    assertion = MagicMock()
    entry.get_assertions.return_value = {assertion}
    trace.add_entry(3, variable, entry)
    statement = MagicMock()
    statement.get_position.return_value = 3
    assert trace.get_assertions(statement) == {assertion}
