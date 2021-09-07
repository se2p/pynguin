#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
from unittest.mock import MagicMock

import pytest

import pynguin.assertion.mutation_analysis.collectorstorage as cs


class Foo:
    def __init__(self, bar):
        self._bar = bar


@pytest.fixture(autouse=True)
def run_before_and_after_tests():
    yield
    cs.CollectorStorage._entries = [[]]
    cs.CollectorStorage._execution_index = 0


def test_insert():
    entry_part1 = {
        cs.CollectorStorage.KEY_TEST_ID: 1,
        cs.CollectorStorage.KEY_POSITION: 1,
        cs.CollectorStorage._get_object_key(0):
            {cs.CollectorStorage.KEY_CLASS_FIELD: {},
             cs.CollectorStorage.KEY_OBJECT_ATTRIBUTE:
                 {'_bar': 'one'}},
        cs.CollectorStorage._get_object_key(1):
            {cs.CollectorStorage.KEY_CLASS_FIELD: {},
             cs.CollectorStorage.KEY_OBJECT_ATTRIBUTE:
                 {'_bar': 'two'}}}
    cs.CollectorStorage.insert(entry_part1)
    entry_part2 = {
        cs.CollectorStorage.KEY_TEST_ID: 1,
        cs.CollectorStorage.KEY_POSITION: 1,
        cs.CollectorStorage.KEY_RETURN_VALUE: 42
    }
    cs.CollectorStorage.insert(entry_part2)
    assert cs.CollectorStorage._entries[0][0] == {**entry_part1, **entry_part2}


def test_append_execution():
    cs.CollectorStorage.append_execution()
    assert cs.CollectorStorage._execution_index == 1
    assert len(cs.CollectorStorage._entries) == 2
    assert cs.CollectorStorage._entries[1] == []


def test_collect_states():
    tc_id = 1
    pos = 1
    objs = [Foo('one'), Foo('two')]
    retval = 42
    cs.CollectorStorage.collect_states(tc_id, pos, objs, {}, retval)
    expected = [
        {
            cs.CollectorStorage.KEY_TEST_ID: tc_id,
            cs.CollectorStorage.KEY_POSITION: pos,
            cs.CollectorStorage.KEY_RETURN_VALUE: retval,
            cs.CollectorStorage._get_object_key(0):
                {cs.CollectorStorage.KEY_CLASS_FIELD: {},
                 cs.CollectorStorage.KEY_OBJECT_ATTRIBUTE:
                     {'_bar': 'one'}
                 },
            cs.CollectorStorage._get_object_key(1):
                {
                    cs.CollectorStorage.KEY_CLASS_FIELD: {},
                    cs.CollectorStorage.KEY_OBJECT_ATTRIBUTE:
                        {'_bar': 'two'}
                }
        }
    ]
    assert expected == cs.CollectorStorage._entries[0]


def test_get_items():
    entry = MagicMock()
    cs.CollectorStorage._entries[0] = entry
    assert cs.CollectorStorage.get_items(0) == entry


def test_get_data_of_mutations():
    entry = MagicMock()
    cs.CollectorStorage._entries[0] = entry
    mut1 = MagicMock()
    cs.CollectorStorage._entries.append(mut1)
    mut2 = MagicMock()
    cs.CollectorStorage._execution_index = 2
    cs.CollectorStorage._entries.append(mut2)
    assert cs.CollectorStorage.get_data_of_mutations() == [mut1, mut2]


def test_get_dataframe_of_mutations():
    entry = MagicMock()
    cs.CollectorStorage._entries[0] = entry
    mut1 = [
        {
            cs.CollectorStorage.KEY_TEST_ID: 1,
            cs.CollectorStorage.KEY_POSITION: 1,
            cs.CollectorStorage.KEY_RETURN_VALUE: 'foo'
        },
        {
            cs.CollectorStorage.KEY_TEST_ID: 0,
            cs.CollectorStorage.KEY_POSITION: 1,
            cs.CollectorStorage.KEY_RETURN_VALUE: 1447
        },
        {
            cs.CollectorStorage.KEY_TEST_ID: 1,
            cs.CollectorStorage.KEY_POSITION: 0,
            cs.CollectorStorage.KEY_RETURN_VALUE: 42
        }
    ]
    cs.CollectorStorage._entries.append(mut1)
    mut2 = [
        {
            cs.CollectorStorage.KEY_TEST_ID: 1,
            cs.CollectorStorage.KEY_POSITION: 1,
            cs.CollectorStorage.KEY_RETURN_VALUE: 'bar'
        },
        {
            cs.CollectorStorage.KEY_TEST_ID: 0,
            cs.CollectorStorage.KEY_POSITION: 1,
            cs.CollectorStorage.KEY_RETURN_VALUE: 42
        },
        {
            cs.CollectorStorage.KEY_TEST_ID: 1,
            cs.CollectorStorage.KEY_POSITION: 0,
            cs.CollectorStorage.KEY_RETURN_VALUE: 1337
        }
    ]
    cs.CollectorStorage._entries.append(mut2)
    cs.CollectorStorage._execution_index = 2
    retval = cs.CollectorStorage.get_dataframe_of_mutations(1, 1)
    expected = [
        {
            cs.CollectorStorage.KEY_TEST_ID: 1,
            cs.CollectorStorage.KEY_POSITION: 1,
            cs.CollectorStorage.KEY_RETURN_VALUE: 'foo'
        },
        {
            cs.CollectorStorage.KEY_TEST_ID: 1,
            cs.CollectorStorage.KEY_POSITION: 1,
            cs.CollectorStorage.KEY_RETURN_VALUE: 'bar'
        }
    ]
    assert retval == expected
