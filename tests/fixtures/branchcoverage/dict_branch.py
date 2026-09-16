#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Fixture module with key-dependent branches in dictionaries and kwargs."""


def check_dict(d: dict[str, int]) -> int:
    """Function that accesses a specific dict key and checks its value."""
    if d["abcd"] == 10:
        return 42
    return 0


def check_kwargs(**kwargs) -> int:
    """Function that accesses kwargs and checks a key."""
    if kwargs["secret"] == 99:
        return 100
    return -1
