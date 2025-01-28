#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import pynguin.utils.collection_utils as cu


def test_dict_without_keys():
    test_dict = {"foo": "bar", "bar": "foo", "test": 123}
    filter_keys = {"test", "bar"}
    result = cu.dict_without_keys(test_dict, filter_keys)
    assert result == {"foo": "bar"}
