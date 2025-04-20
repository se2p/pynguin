#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
# Adapted from
# https://github.com/KmolYuan/apimd/blob/f23060a996adcc30552b4e93c49804640e4c4c95/apimd/compiler.py#L119
from collections.abc import Iterable


def table_row(*items: Iterable[str]) -> str:
    """Make the row to a pipe table."""

    def table(_items: Iterable[str], space: bool = True) -> str:
        s = " " if space else ""
        return "|" + s + (s + "|" + s).join(_items) + s + "|\n"

    return table(name for name in items[0])
