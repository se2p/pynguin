#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#

"""Provides some common utilities for instrumentation."""

from __future__ import annotations

import enum

from abc import abstractmethod
from dataclasses import dataclass
from opcode import opmap
from typing import TYPE_CHECKING
from typing import Any
from typing import Protocol


if TYPE_CHECKING:
    from bytecode.instr import _UNSET
    from bytecode.instr import Instr

    from pynguin.instrumentation import PynguinCompare
    from pynguin.instrumentation import controlflow as cf


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

    value: int | str | bool | enum.Enum | None


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


class ConvertInstrumentationMethodCallFunction(Protocol):
    """Represents a function that converts an instrumentation method call to instructions."""

    @abstractmethod
    def __call__(
        self,
        instrumentation_method_call: InstrumentationMethodCall,
        lineno: int | _UNSET | None,
    ) -> tuple[cf.ArtificialInstr, ...]:
        """Convert an instrumentation method call to instructions.

        Args:
            instrumentation_method_call: The method call to convert.
            lineno: The line number for the instruction.

        Returns:
            A tuple of artificial instructions representing the method call.
        """


class ConvertInstrumentationCopyFunction(Protocol):
    """Represents a function that converts an instrumentation copy to instructions."""

    @abstractmethod
    def __call__(
        self,
        instrumentation_copy: InstrumentationCopy,
        lineno: int | _UNSET | None,
    ) -> tuple[cf.ArtificialInstr, ...]:
        """Convert an instrumentation copy to instructions.

        Args:
            instrumentation_copy: The copy to convert.
            lineno: The line number for the instruction.

        Returns:
            A tuple of artificial instructions representing the copy.
        """


class ExtractComparisonFunction(Protocol):
    """Represents a function that extracts a comparison from an instruction."""

    @abstractmethod
    def __call__(self, instr: Instr) -> PynguinCompare:
        """Extract the comparison from an instruction.

        Args:
            instr: The instruction to extract the comparison from.

        Returns:
            The comparison extracted from the instruction.
        """


class CreateAddInstructionFunction(Protocol):
    """Represents a function that creates an add instruction."""

    @abstractmethod
    def __call__(self, lineno: int | _UNSET | None) -> cf.ArtificialInstr:
        """Create an add instruction.

        Args:
            lineno: The line number for the instruction.

        Returns:
            An artificial instruction representing the add operation.
        """


class CheckedCoverageInstrumentationVisitorMethod(Protocol):
    """Represents a visitor method used in checked coverage instrumentation."""

    @abstractmethod
    def __call__(  # noqa: PLR0917
        _self,  # noqa: N805
        self,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
        instr_offset: int,
    ) -> None:
        """Visit an instruction in the control flow graph.

        Args:
            self: The instance of the checked coverage instrumentation.
            cfg: The control flow graph.
            code_object_id: The code object id of the containing code object.
            node: The node in the control flow graph.
            instr: The instruction being visited.
            instr_index: The index of the instruction in the basic block.
            instr_offset: The offset of the instruction in the bytecode.
        """


def to_opcodes(*names: str) -> tuple[int, ...]:
    """Convert a tuple of opcode names to their corresponding integer values.

    Args:
        names: The names of the opcodes to convert.

    Returns:
        A tuple of integers representing the opcodes.
    """
    return tuple(opmap[name] for name in names)


def before(index: int) -> slice[int, int]:
    """Get the slice for inserting an instruction before the given index.

    Args:
        index: The index of the instruction

    Returns:
        A slice for inserting an instruction before the given index.
    """
    return slice(index, index)


def after(index: int) -> slice[int, int]:
    """Get the slice for inserting an instruction after the given index.

    Args:
        index: The index of the instruction

    Returns:
        A slice for inserting an instruction after the given index.
    """
    return slice(index + 1, index + 1)


def override(index: int) -> slice[int, int]:
    """Get the slice for overriding an instruction at the given index.

    Args:
        index: The index of the instruction

    Returns:
        A slice for overriding an instruction at the given index.
    """
    return slice(index, index + 1)


AST_FILENAME = "<ast>"
