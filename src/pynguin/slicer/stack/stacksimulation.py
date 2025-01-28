#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
# Idea and structure are taken from the pyChecco project, see:
# https://github.com/ipsw1/pychecco
"""Provides classes to simulate the stack during dynamic slicing."""

from __future__ import annotations

from collections import UserList
from dataclasses import dataclass
from dataclasses import field
from typing import TYPE_CHECKING

import pynguin.utils.opcodes as op


if TYPE_CHECKING:
    from pynguin.slicer.executionflowbuilder import UniqueInstruction

DEFAULT_STACK_HEIGHT = 40
DEFAULT_FRAME_HEIGHT = 40


class BlockStack(UserList):
    """Represents the stack for a block in a frame."""

    def push(self, instr: UniqueInstruction) -> None:
        """Push an instruction onto the stack."""
        self.append(instr)

    def peek(self) -> UniqueInstruction | None:
        """Return the instruction on top of the stack without removing it.

        Returns:
            The instruction on top of the stack, None, if stack is empty.
        """
        try:
            return self[-1]
        except IndexError:
            return None


@dataclass
class FrameStack:
    """Represents the stack for a frame in the frame stack of frames."""

    code_object_id: int
    block_stacks: list[BlockStack]
    attribute_uses: set[str] = field(default_factory=set)
    import_name_instr: UniqueInstruction | None = None


class TraceStack:
    """Simulates the tracing on the stack."""

    def __init__(self):  # noqa: D107
        self.frame_stacks: list[FrameStack] = []
        self._reset()
        self._prepare_stack()

    def _reset(self) -> None:
        """Remove all frame stacks from this trace."""
        self.frame_stacks.clear()

    def _prepare_stack(self) -> None:
        # Since we do not exactly know what the stack state at the slicing criterion is
        # and because the behavior is reversed, we fill the stack with some frames
        # (having some block stacks inside them)
        for _ in range(DEFAULT_STACK_HEIGHT):
            frame_stack = FrameStack(-1, [])
            for _ in range(DEFAULT_FRAME_HEIGHT):
                block_stack = BlockStack([])
                frame_stack.block_stacks.append(block_stack)
            self.frame_stacks.append(frame_stack)

    def push_stack(self, code_object_id: int) -> None:
        """Add a frame stack for the given code object id."""
        self.frame_stacks.append(FrameStack(code_object_id, [BlockStack([])]))

    def push_artificial_stack(self) -> None:
        """Add a frame stack for a non-existing code object id.

        Signaling, this stack is artificial and not part of the byte code.
        """
        self.push_stack(code_object_id=-1)

    def pop_stack(self) -> None:
        """Return the frame stack on top of the stack of FrameStacks."""
        # TOS from the frame stack is popped
        frame = self.frame_stacks.pop()
        if frame.code_object_id != -1:
            # A non-dummy frame can only have one block_stack at the end of execution
            assert len(frame.block_stacks) == 1, "More than one block on a popped stack"

    def update_push_operations(self, num_pushes: int, *, returned: bool) -> tuple[bool, bool]:
        """Simulate the push operations on the stack.

        Returns whether implicit dependencies occur or uses are included.

        Args:
            num_pushes: number of pushes to pop from stack
            returned: Whether the trace already returned from the method call

        Returns:
            A tuple containing the booleans:
                1. implicit dependency
                2. include use
        """
        curr_frame_stack = self.frame_stacks[-1]
        curr_block_stack = curr_frame_stack.block_stacks[-1]

        imp_dependency: bool = False
        include_use: bool = True

        if returned:
            prev_frame_stack = self.frame_stacks[-2]
            prev_block_stack_instr = prev_frame_stack.block_stacks[-1].peek()
            if prev_block_stack_instr and prev_block_stack_instr.in_slice:
                imp_dependency = True

        # Handle push operations
        for _ in range(num_pushes):
            try:
                tos_instr = curr_block_stack.pop()
            except IndexError:
                # Started backward tracing not at the end of execution. In forward
                # direction this corresponds to popping from an empty stack when
                # starting the execution at an arbitrary point. For slicing this can of
                # course happen all the time, so this is not a problem
                tos_instr = None

            if tos_instr and tos_instr.in_slice:
                imp_dependency = True

                # For attribute accesses, instructions preparing TOS to access the
                # attribute should be included. However, the use data for these will
                # not be searched for, since this would widen the scope of the search
                # for complete objects rather than only for the attribute thereof.
                if (
                    tos_instr.opcode in {op.STORE_ATTR, op.STORE_SUBSCR}
                    and len(curr_block_stack) > 0
                ):
                    tos1_instr = curr_block_stack.peek()
                    if tos1_instr and tos1_instr.opcode == tos_instr.opcode:
                        include_use = False
                if tos_instr.opcode in {op.LOAD_ATTR, op.DELETE_ATTR, op.IMPORT_FROM}:
                    include_use = False

        return imp_dependency, include_use

    def update_pop_operations(
        self, num_pops: int, unique_instr: UniqueInstruction, *, in_slice: bool
    ) -> None:
        """Pushes a given number of instructions onto the stack.

        Additionally, updates the 'in_slice' attribute of the instruction.

        Args:
            num_pops: number of pop operations
            unique_instr: the instruction for which the stack is updated
            in_slice: whether the instruction is part of the slice
        """
        curr_frame_stack = self.frame_stacks[-1]
        curr_block_stack = curr_frame_stack.block_stacks[-1]

        if in_slice:
            unique_instr.in_slice = True

        # Handle pop operations
        for _ in range(num_pops):
            curr_block_stack.push(unique_instr)

    def get_attribute_uses(self):
        """Get the attribute uses of the top of the stack.

        Returns:
            The attribute uses of the top of the stack, none if frame stacks are empty.
        """
        return self.frame_stacks[-1].attribute_uses

    def set_attribute_uses(self, attribute_uses: set[str]) -> None:
        """Set attribute uses of frame stack on top of stack."""
        self.frame_stacks[-1].attribute_uses = set()
        for attr in attribute_uses:
            self.frame_stacks[-1].attribute_uses.add(attr)

    def get_import_frame(self) -> UniqueInstruction | None:
        """Get the import frame instruction, None if frame stacks are empty."""
        return self.frame_stacks[-1].import_name_instr

    def set_import_frame(self, import_name_instr: UniqueInstruction | None):
        """Set import name instruction of frame stack on top of stack."""
        self.frame_stacks[-1].import_name_instr = import_name_instr
