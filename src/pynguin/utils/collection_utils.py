#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Utility methods for collections."""

from __future__ import annotations

from typing import Any


def dict_without_keys(dict_to_change: dict[Any, Any], keys: set[Any]) -> dict[Any, Any]:
    """Removes the given keys from the given dict.

    Args:
        dict_to_change: The dict where the keys should be removed.
        keys: The list of keys which should be removed.

    Returns:
        the dict without the specified keys.
    """
    return {k: v for k, v in dict_to_change.items() if k not in keys}
