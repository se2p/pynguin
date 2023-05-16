#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2023 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Contains all code related to executed instruction classes."""
from __future__ import annotations

from dataclasses import dataclass

from opcode import opname


@dataclass(frozen=True)
class ExecutedInstruction:
    """Represents an executed bytecode instruction with additional information."""

    file: str
    code_object_id: int
    node_id: int
    opcode: int
    argument: int | str | None
    lineno: int
    offset: int

    @property
    def name(self) -> str:
        """Returns the name of the executed instruction.

        Returns:
            The name of the executed instruction.
        """
        return opname[self.opcode]

    @staticmethod
    def is_jump() -> bool:
        """Returns whether the executed instruction is a jump condition.

        Returns:
            True, if the instruction is a jump condition, False otherwise.
        """
        return False

    def __str__(self) -> str:
        return (
            f"{'(-)':<7} {self.file:<40} {opname[self.opcode]:<72} "
            f"{self.code_object_id:02d} @ line: {self.lineno:d}-{self.offset:d}"
        )


@dataclass(frozen=True)
class ExecutedMemoryInstruction(ExecutedInstruction):
    """Represents an executed instructions which read from or wrote to memory."""

    arg_address: int
    is_mutable_type: bool
    object_creation: bool

    def __str__(self) -> str:
        if not self.arg_address:
            arg_address = -1
        else:
            arg_address = self.arg_address
        return (
            f"{'(mem)':<7} {self.file:<40} {opname[self.opcode]:<20} "
            f"{self.argument:<25} {hex(arg_address):<25} {self.code_object_id:02d}"
            f"@ line: {self.lineno:d}-{self.offset:d}"
        )


@dataclass(frozen=True)
class ExecutedAttributeInstruction(ExecutedInstruction):
    """Represents an executed instructions which accessed an attribute.

    We prepend each accessed attribute with the address of the object the attribute
    is taken from. This allows to build correct def-use pairs during backward traversal.
    """

    src_address: int
    arg_address: int
    is_mutable_type: bool

    @property
    def combined_attr(self):
        """Format the source address and the argument for an instruction.

        Returns:
            A string representation of the attribute in memory
        """
        return f"{hex(self.src_address)}_{self.argument}"

    def __str__(self) -> str:
        return (
            f"{'(attr)':<7} {self.file:<40} {opname[self.opcode]:<20} "
            f"{self.combined_attr:<51} {self.code_object_id:02d} "
            f"@ line: {self.lineno:d}-{self.offset:d}"
        )


@dataclass(frozen=True)
class ExecutedControlInstruction(ExecutedInstruction):
    """Represents an executed control flow instruction."""

    @staticmethod
    def is_jump() -> bool:
        """Returns whether the executed instruction is a jump condition.

        Returns:
            True, if the instruction is a jump condition, False otherwise.
        """
        return True

    def __str__(self) -> str:
        return (
            f"{'(crtl)':<7} {self.file:<40} {opname[self.opcode]:<20} "
            f"{self.argument:<51} {self.code_object_id:02d} "
            f"@ line: {self.lineno:d}-{self.offset:d}"
        )


@dataclass(frozen=True)
class ExecutedCallInstruction(ExecutedInstruction):
    """Represents an executed call instruction."""

    def __str__(self) -> str:
        return (
            f"{'(func)':<7} {self.file:<40} {opname[self.opcode]:<72} "
            f"{self.code_object_id:02d} @ line: {self.lineno:d}-{self.offset:d}"
        )


@dataclass(frozen=True)
class ExecutedReturnInstruction(ExecutedInstruction):
    """Represents an executed return instruction."""

    def __str__(self) -> str:
        return (
            f"{'(ret)':<7} {self.file:<40} {opname[self.opcode]:<72} "
            f"{self.code_object_id:02d} @ line: {self.lineno:d}-{self.offset:d}"
        )
