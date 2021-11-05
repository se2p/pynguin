#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
from unittest import mock
from unittest.mock import MagicMock

import pytest

import pynguin.assertion.mutation_analysis.collectorstorage as cs


class Foo:
    _foo = 42

    def __init__(self, bar):
        self._bar = bar


def test_collect_return_value():
    storage = cs.CollectorStorage()
    storage.append_execution()
    statement = MagicMock()
    storage._collect_return_value(statement, "foo")
    assert storage._storage[0][(cs.EntryTypes.RETURN_VALUE, statement)] == "foo"


def test_collect_objects_attr():
    storage = cs.CollectorStorage()
    storage.append_execution()
    statement = MagicMock()
    vr = MagicMock()
    storage._collect_objects(statement, {vr: Foo(2)})
    assert (
        storage._storage[0][(cs.EntryTypes.OBJECT_ATTRIBUTE, statement, vr, "_bar")]
        == 2
    )
    assert (
        storage._storage[0][(cs.EntryTypes.CLASS_FIELD, statement, Foo, "_foo")] == 42
    )


@mock.patch("builtins.vars", return_value={"foo": 123, "bar": 321})
def test_collect_globals(vars_mock):
    storage = cs.CollectorStorage()
    storage.append_execution()
    statement = MagicMock()
    modules = {"alias": MagicMock(__name__="test")}
    storage._collect_globals(statement, modules)
    assert (
        storage._storage[0][(cs.EntryTypes.GLOBAL_FIELD, statement, "test", "foo")]
        == 123
    )
    assert (
        storage._storage[0][(cs.EntryTypes.GLOBAL_FIELD, statement, "test", "bar")]
        == 321
    )


def test_append_execution():
    storage = cs.CollectorStorage()
    storage.append_execution()
    storage.append_execution()
    assert len(storage._storage) == 2
    assert storage._storage[0] == {}
    assert storage._storage[1] == {}


def test_get_execution_entry():
    storage = cs.CollectorStorage()
    storage.append_execution()
    assert {} == storage.get_execution_entry(0)


def test_get_execution_entry_exception():
    storage = cs.CollectorStorage()
    with pytest.raises(IndexError):
        storage.get_execution_entry(0)


def test_get_mutations():
    storage = cs.CollectorStorage()
    statement = MagicMock()
    storage.append_execution()
    storage._collect_return_value(statement, "foo")
    storage.append_execution()
    storage._collect_return_value(statement, "pynguin")
    storage.append_execution()
    storage._collect_return_value(statement, "bar")
    storage.append_execution()
    storage._collect_return_value(statement, "test")
    key = (cs.EntryTypes.RETURN_VALUE, statement)
    assert storage.get_mutations(key) == ["pynguin", "bar", "test"]
