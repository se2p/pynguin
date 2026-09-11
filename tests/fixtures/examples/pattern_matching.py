#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Example fixture containing pattern matching functions."""

from __future__ import annotations


def match_sequence_example(val: object) -> int:
    """Matches a sequence pattern.

    Args:
        val: The input value.

    Returns:
        1 if sequence of length 2, 0 otherwise.
    """
    match val:
        case [_, _]:
            return 1
        case _:
            return 0


def match_mapping_example(val: object) -> int:
    """Matches a mapping pattern with keys.

    Args:
        val: The input value.

    Returns:
        1 if mapping with keys a and b, 0 otherwise.
    """
    match val:
        case {"a": 1, "b": 2}:
            return 1
        case _:
            return 0
