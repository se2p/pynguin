#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
from unittest.mock import MagicMock

import pynguin.assertion.mutation_analysis.collectorstorage as cs


class Foo:
    def __init__(self, bar):
        self._bar = bar


def test_insert():
    storage = cs.CollectorStorage()
    entry_part1 = {
        cs.KEY_TEST_ID: 1,
        cs.KEY_POSITION: 1,
        storage._get_object_key(0): {
            cs.KEY_CLASS_FIELD: {},
            cs.KEY_OBJECT_ATTRIBUTE: {"_bar": "one"},
        },
        storage._get_object_key(1): {
            cs.KEY_CLASS_FIELD: {},
            cs.KEY_OBJECT_ATTRIBUTE: {"_bar": "two"},
        },
    }
    storage.insert(entry_part1)
    entry_part2 = {
        cs.KEY_TEST_ID: 1,
        cs.KEY_POSITION: 1,
        cs.KEY_RETURN_VALUE: 42,
    }
    storage.insert(entry_part2)
    assert storage._entries[0][0] == {**entry_part1, **entry_part2}


def test_append_execution():
    storage = cs.CollectorStorage()
    storage.append_execution()
    assert storage._execution_index == 1
    assert len(storage._entries) == 2
    assert storage._entries[1] == []


def test_collect_states():
    tc_id = 1
    pos = 1
    objs = [Foo("one"), Foo("two")]
    retval = 42
    storage = cs.CollectorStorage()
    storage.collect_states(tc_id, pos, objs, {}, retval)
    expected = [
        {
            cs.KEY_TEST_ID: tc_id,
            cs.KEY_POSITION: pos,
            cs.KEY_RETURN_VALUE: retval,
            storage._get_object_key(0): {
                cs.KEY_CLASS_FIELD: {},
                cs.KEY_OBJECT_ATTRIBUTE: {"_bar": "one"},
            },
            storage._get_object_key(1): {
                cs.KEY_CLASS_FIELD: {},
                cs.KEY_OBJECT_ATTRIBUTE: {"_bar": "two"},
            },
        }
    ]
    assert expected == storage._entries[0]


def test_get_items():
    entry = MagicMock()
    storage = cs.CollectorStorage()
    storage._entries[0] = entry
    assert storage.get_items(0) == entry


def test_get_data_of_mutations():
    storage = cs.CollectorStorage()
    entry = MagicMock()
    storage._entries[0] = entry
    mut1 = MagicMock()
    storage._entries.append(mut1)
    mut2 = MagicMock()
    storage._execution_index = 2
    storage._entries.append(mut2)
    assert storage.get_data_of_mutations() == [mut1, mut2]


def test_get_dataframe_of_mutations():
    storage = cs.CollectorStorage()
    entry = MagicMock()
    storage._entries[0] = entry
    mut1 = [
        {
            cs.KEY_TEST_ID: 1,
            cs.KEY_POSITION: 1,
            cs.KEY_RETURN_VALUE: "foo",
        },
        {
            cs.KEY_TEST_ID: 0,
            cs.KEY_POSITION: 1,
            cs.KEY_RETURN_VALUE: 1447,
        },
        {
            cs.KEY_TEST_ID: 1,
            cs.KEY_POSITION: 0,
            cs.KEY_RETURN_VALUE: 42,
        },
    ]
    storage._entries.append(mut1)
    mut2 = [
        {
            cs.KEY_TEST_ID: 1,
            cs.KEY_POSITION: 1,
            cs.KEY_RETURN_VALUE: "bar",
        },
        {
            cs.KEY_TEST_ID: 0,
            cs.KEY_POSITION: 1,
            cs.KEY_RETURN_VALUE: 42,
        },
        {
            cs.KEY_TEST_ID: 1,
            cs.KEY_POSITION: 0,
            cs.KEY_RETURN_VALUE: 1337,
        },
    ]
    storage._entries.append(mut2)
    storage._execution_index = 2
    retval = storage.get_dataframe_of_mutations(1, 1)
    expected = [
        {
            cs.KEY_TEST_ID: 1,
            cs.KEY_POSITION: 1,
            cs.KEY_RETURN_VALUE: "foo",
        },
        {
            cs.KEY_TEST_ID: 1,
            cs.KEY_POSITION: 1,
            cs.KEY_RETURN_VALUE: "bar",
        },
    ]
    assert retval == expected
