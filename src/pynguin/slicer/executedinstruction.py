#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
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
    argument: int | str | tuple[str, str] | None
    lineno: int
    instr_original_index: int

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
            f"{self.code_object_id:02d} @ line: {self.lineno:d}-{self.instr_original_index:d}"
        )


@dataclass(frozen=True)
class ExecutedMemoryInstruction(ExecutedInstruction):
    """Represents an executed instructions which read from or wrote to memory."""

    arg_address: int | tuple[int, int]
    is_mutable_type: bool | tuple[bool, bool]
    object_creation: bool | tuple[bool, bool]

    def __str__(self) -> str:
        arg_address = self.arg_address or -1
        hex_address = (
            hex(arg_address)
            if isinstance(arg_address, int)
            else (hex(arg_address[0]), hex(arg_address[1]))
        )
        return (
            f"{'(mem)':<7} {self.file:<40} {opname[self.opcode]:<20} "
            f"{self.argument:<25} {hex_address:<25} {self.code_object_id:02d}"
            f"@ line: {self.lineno:d}-{self.instr_original_index:d}"
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
    is_method: bool

    @property
    def combined_attr(self):
        """Format the source address and the argument for an instruction.

        Returns:
            A string representation of the attribute in memory
        """
        return f"{hex(self.src_address)}_{self.argument}"

    def __str__(self) -> str:
        return (
            f"{'(meth)' if self.is_method else '(attr)':<7} {self.file:<40} "
            f"{opname[self.opcode]:<20} {self.combined_attr:<51} {self.code_object_id:02d} "
            f"@ line: {self.lineno:d}-{self.instr_original_index:d}"
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
            f"@ line: {self.lineno:d}-{self.instr_original_index:d}"
        )


@dataclass(frozen=True)
class ExecutedCallInstruction(ExecutedInstruction):
    """Represents an executed call instruction."""

    def __str__(self) -> str:
        return (
            f"{'(func)':<7} {self.file:<40} {opname[self.opcode]:<72} "
            f"{self.code_object_id:02d} @ line: {self.lineno:d}-{self.instr_original_index:d}"
        )


@dataclass(frozen=True)
class ExecutedReturnInstruction(ExecutedInstruction):
    """Represents an executed return instruction."""

    def __str__(self) -> str:
        return (
            f"{'(ret)':<7} {self.file:<40} {opname[self.opcode]:<72} "
            f"{self.code_object_id:02d} @ line: {self.lineno:d}-{self.instr_original_index:d}"
        )
