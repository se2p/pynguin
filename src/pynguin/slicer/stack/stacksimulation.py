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

import logging
from collections import UserList
from dataclasses import dataclass, field

from pynguin.instrumentation.version import ACCESS_NAMES, STORE_NAMES
from pynguin.slicer.executionflowbuilder import UniqueInstruction

DEFAULT_STACK_HEIGHT = 40
DEFAULT_FRAME_HEIGHT = 40


class BlockStack(UserList[tuple[UniqueInstruction, bool]]):
    """Represents the stack for a block in a frame."""

    def push(self, instr: UniqueInstruction, in_slice: bool) -> None:  # noqa: FBT001
        """Push an instruction onto the stack.

        Args:
            instr: The instruction to push onto the stack.
            in_slice: Whether the instruction is part of the slice.
        """
        self.append((instr, in_slice))

    def peek(self) -> tuple[UniqueInstruction, bool] | None:
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

    @property
    def last_block(self) -> BlockStack:
        """Return the last block stack of this frame stack.

        Raises:
            IndexError: If the frame stack is empty.

        Returns:
            The last block stack of this frame stack.
        """
        return self.block_stacks[-1]


class TraceStack:
    """Simulates the tracing on the stack."""

    _logger = logging.getLogger(__name__)

    def __init__(self):  # noqa: D107
        self.frame_stacks: list[FrameStack] = []
        self._reset()
        self._prepare_stack()

    @property
    def last_frame_stack(self) -> FrameStack:
        """Return the last frame stack.

        Raises:
            IndexError: If the stack is empty.

        Returns:
            The last frame stack.
        """
        return self.frame_stacks[-1]

    @property
    def caller_frame_stack(self) -> FrameStack:
        """Return the caller frame stack, i.e., the one before the last one.

        Raises:
            IndexError: If the stack is empty or has only one frame.

        Returns:
            The caller frame stack.
        """
        return self.frame_stacks[-2]

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
        imp_dependency: bool = False
        include_use: bool = True

        if returned:
            match self.caller_frame_stack.last_block.peek():
                case (caller_block_stack_instr, True):
                    self._logger.debug(
                        "IMPLICIT DEPENDENCY (IN SLICE METHOD CALL RETURN): %s",
                        caller_block_stack_instr,
                    )
                    imp_dependency = True

        if num_pushes > 0:
            self._logger.debug("STACK POPPING: [%s time(s)]", num_pushes)

        curr_block_stack = self.last_frame_stack.last_block
        for _ in range(num_pushes):
            tos_instr: UniqueInstruction | None
            try:
                tos_instr, in_slice = curr_block_stack.pop()
            except IndexError:
                # Started backward tracing not at the end of execution. In forward
                # direction this corresponds to popping from an empty stack when
                # starting the execution at an arbitrary point. For slicing this can of
                # course happen all the time, so this is not a problem
                tos_instr = None
                in_slice = False

            self._logger.debug(
                "POP (%s): %s",
                "IN SLICE" if in_slice else "NOT IN SLICE",
                tos_instr,
            )
            if tos_instr is not None and in_slice:
                self._logger.debug("IMPLICIT DEPENDENCY (IN SLICE): %s", tos_instr)
                imp_dependency = True

                # For attribute accesses, instructions preparing TOS to access the
                # attribute should be included. However, the use data for these will
                # not be searched for, since this would widen the scope of the search
                # for complete objects rather than only for the attribute thereof.
                if tos_instr.name in STORE_NAMES and len(curr_block_stack) > 0:
                    match curr_block_stack.peek():
                        case (tos1_instr, True) if tos1_instr.name in STORE_NAMES:  # type: ignore[union-attr]
                            self._logger.debug(
                                "DISABLED INCLUDE USE (STORE INSTRUCTION): %s", tos1_instr
                            )
                            include_use = False
                if tos_instr.name in ACCESS_NAMES and not tos_instr.is_method:
                    self._logger.debug("DISABLED INCLUDE USE (ACCESS INSTRUCTION): %s", tos_instr)
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
        if num_pops > 0:
            self._logger.debug(
                "STACK PUSHING (%s): [%s time(s)] %s",
                "IN SLICE" if in_slice else "NOT IN SLICE",
                num_pops,
                unique_instr,
            )

        curr_block_stack = self.last_frame_stack.last_block
        for _ in range(num_pops):
            curr_block_stack.push(unique_instr, in_slice)
