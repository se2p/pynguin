#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Utility methods for collections."""
from typing import Any, Dict, List


def filter_dictlist_by_dict(
    dict_filter: Dict[Any, Any], list_to_filter: List[Dict[Any, Any]]
) -> List[Dict[Any, Any]]:
    """
    Filters a given list of dicts with a dict and returns a list of dict with all dicts
    of the list which contain the same key and values as the filter.

    Args:
        dict_filter: The dict which contains the things for which the list should
                     be filtered.
        list_to_filter: The list of dicts which should be filtered.

    Returns:
        the resulting list of dicts.
    """
    return [
        i
        for i in list_to_filter
        if all(
            i[target_key] == target_value
            for target_key, target_value in dict_filter.items()
        )
    ]


def dict_without_keys(
    dict_to_change: Dict[Any, Any], keys: List[Any]
) -> Dict[Any, Any]:
    """
    Removes the given keys from the given dict.

    Args:
        dict_to_change: The dict where the keys should be removed.
        keys: The list of keys which should be removed.

    Returns:
        the dict without the specified keys.
    """
    return {k: v for k, v in dict_to_change.items() if k not in keys}
