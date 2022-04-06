#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
# Idea and structure are taken from the pyChecco project, see:
# https://github.com/ipsw1/pychecco
"""Provides classes and enums to track instructions during slicing"""

import dis

from bytecode import Instr

import pynguin.utils.opcodes as op
from pynguin.testcase.execution import CodeObjectMetaData
from pynguin.utils.exceptions import InstructionNotFoundException

UNSET = object()


class UniqueInstruction(Instr):
    """
    The UniqueInstruction is a representation for concrete occurrences of instructions.
    It combines multiple information sources, including the corresponding
    instruction in the disassembly.
    """

    def __init__(  # pylint: disable=too-many-arguments
        self,
        file: str,
        name: str,
        code_object_id: int,
        node_id: int,
        code_meta: CodeObjectMetaData,
        offset: int,
        arg=UNSET,
        lineno: int = None,
        in_slice: bool = False,
    ):
        self.file = file
        if arg is not UNSET:
            super().__init__(name, arg, lineno=lineno)
        else:
            super().__init__(name, lineno=lineno)
        self.code_object_id = code_object_id
        self.node_id = node_id
        self.offset = offset

        # Additional information from disassembly
        dis_instr = self.locate_in_disassembly(
            list(dis.get_instructions(code_meta.code_object))
        )
        self.dis_arg = dis_instr.arg
        self.is_jump_target = dis_instr.is_jump_target

        self._in_slice = in_slice

    @property
    def in_slice(self) -> bool:
        """Returns a boolean if the instruction is inside the slice.

        Returns:
            True if the instructions is part of the slice, False otherwise.
        """
        return self._in_slice

    @in_slice.setter
    def in_slice(self, in_slice) -> None:
        """Sets whether the instruction is inside the slice

        Args:
            in_slice: whether the instruction is inside the slice
        """
        self._in_slice = in_slice

    def is_def(self) -> bool:
        """Returns a boolean if the instruction is a definition.

        Returns:
            True if the instructions is a definition, False otherwise.
        """
        return self.opcode in op.MEMORY_DEF_INSTRUCTIONS

    def is_use(self) -> bool:
        """Returns a boolean if the instruction is a use.

        Returns:
            True if the instructions is a use, False otherwise.
        """
        return self.opcode in op.MEMORY_USE_INSTRUCTIONS

    def is_cond_branch(self) -> bool:
        """Returns a boolean if the instruction is a conditional branching.

        Returns:
            True if the instructions is a conditional branching, False otherwise.
        """
        return self.opcode in op.COND_BRANCH_INSTRUCTIONS

    def locate_in_disassembly(self, disassembly) -> dis.Instruction:
        """Retrieves the instruction inside disassembled bytecode.

        Args:
            disassembly: the disassembled bytecode containing the instruction

        Returns:
            The instruction from withing the bytecode.

        Raises:
            InstructionNotFoundException: If the instruction is not
                located in the code object.
        """
        # EXTENDED_ARG instructions are not counted for instrumented offsets,
        # which has to be compensated here
        offset_offset = 0

        for dis_instr in disassembly:
            if dis_instr.opcode == op.EXTENDED_ARG:
                offset_offset += 2

            if dis_instr.opcode == self.opcode and dis_instr.offset == (
                self.offset + offset_offset
            ):
                return dis_instr

        raise InstructionNotFoundException

    def __hash__(self):
        return hash((self.name, self.code_object_id, self.node_id, self.offset))
