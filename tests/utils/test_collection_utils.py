#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
import pynguin.utils.collection_utils as cu


def test_filter_dictlist_by_dict():
    dict_filter = {"id": 0, "foo": "bar"}
    list_to_filter = [
        {"id": 0, "foo": "bar", "test": 123},
        {"id": 0, "foo": "bar", "test2": 0},
        {"id": 1, "foo": "bar", "test": 123},
        {"id": 1, "foo": "foo", "test": 123},
        {"id": 0, "foo": "foo", "test": 123},
    ]
    result = cu.filter_dictlist_by_dict(dict_filter, list_to_filter)
    assert result == [
        {"id": 0, "foo": "bar", "test": 123},
        {"id": 0, "foo": "bar", "test2": 0},
    ]


def test_dict_without_keys():
    test_dict = {"foo": "bar", "bar": "foo", "test": 123}
    filter_keys = {"test", "bar"}
    result = cu.dict_without_keys(test_dict, filter_keys)
    assert result == {"foo": "bar"}
