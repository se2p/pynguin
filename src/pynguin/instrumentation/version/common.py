#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#

"""Provides some common utilities for instrumentation."""

from __future__ import annotations

import enum

from dataclasses import dataclass
from opcode import opmap
from typing import Any


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


def to_opcodes(*names: str) -> tuple[int, ...]:
    """Convert a tuple of opcode names to their corresponding integer values.

    Args:
        names: The names of the opcodes to convert.

    Returns:
        A tuple of integers representing the opcodes.
    """
    return tuple(opmap[name] for name in names)
