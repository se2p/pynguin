#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides the instrumentation mechanisms."""

from __future__ import annotations

import enum

from dataclasses import dataclass
from typing import Any
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


class InstrumentationCopy(enum.IntEnum):
    """An enum to represent what should be copied in instrumentation."""

    FIRST = enum.auto()
    """The first element of the stack is copied."""

    FIRST_DOWN_TWO = enum.auto()
    """The first element of the stack is copied, and is moved down two times."""

    SECOND = enum.auto()
    """The second element of the stack is copied."""

    SECOND_DOWN_TWO = enum.auto()
    """The second element of the stack is copied, and is moved down two times."""

    SECOND_DOWN_THREE = enum.auto()
    """The second element of the stack is copied, and is moved down three times."""

    TWO_FIRST = enum.auto()
    """The two first elements of the stack are copied."""

    TWO_FIRST_REVERSED = enum.auto()
    """The two first elements of the stack are copied, but in reversed order."""


class InstrumentationStackValue(enum.IntEnum):
    """Represents a stack value in instrumentation."""

    FIRST = 1
    """The first value on the stack."""

    SECOND = 2
    """The second value on the stack."""


@dataclass(frozen=True)
class InstrumentationConstantLoad:
    """Represents a constant load used in instrumentation."""

    value: int | str | bool | None


@dataclass(frozen=True)
class InstrumentationFastLoad:
    """Represents a fast load used in instrumentation."""

    name: str


@dataclass(frozen=True)
class InstrumentationNameLoad:
    """Represents a name load used in instrumentation."""

    name: str


@dataclass(frozen=True)
class InstrumentationGlobalLoad:
    """Represents a global load used in instrumentation."""

    name: str


@dataclass(frozen=True)
class InstrumentationDeref:
    """Represents a reference used in instrumentation."""

    name: str


@dataclass(frozen=True)
class InstrumentationClassDeref:
    """Represents a class reference used in instrumentation."""

    name: str


@dataclass(frozen=True)
class InstrumentationMethodCall:
    """Represents a method call used in instrumentation."""

    self: Any
    method_name: str
    args: tuple[InstrumentationArgument, ...]


InstrumentationArgument = (
    InstrumentationConstantLoad
    | InstrumentationFastLoad
    | InstrumentationNameLoad
    | InstrumentationGlobalLoad
    | InstrumentationStackValue
    | InstrumentationDeref
    | InstrumentationClassDeref
)
