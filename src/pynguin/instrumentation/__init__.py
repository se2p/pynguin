#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides the instrumentation mechanisms."""

from __future__ import annotations

import enum

from typing import NamedTuple


@enum.unique
class PynguinCompare(enum.IntEnum):
    """Enum of all compare operations.

    Previously we were able to use a similar enum from the bytecode library,
    because upto 3.8, there was only a single compare op. With 3.9+, there are now some
    separate compare ops, e.g., IS_OP or CONTAINS_OP. Therefore, we recreate the
    original enum here and map these new ops back.
    """

    LT = 0
    LE = 1
    EQ = 2
    NE = 3
    GT = 4
    GE = 5
    IN = 6
    NOT_IN = 7
    IS = 8
    IS_NOT = 9
    EXC_MATCH = 10


class StackEffect(NamedTuple):
    """A named tuple to represent the stack effect of an opcode."""

    pops: int
    pushes: int
