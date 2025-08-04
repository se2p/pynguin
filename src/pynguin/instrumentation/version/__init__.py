#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides some version-specific utilities for instrumentation handling."""

from __future__ import annotations

import sys

from abc import abstractmethod
from typing import TYPE_CHECKING
from typing import Protocol


if TYPE_CHECKING:
    from collections.abc import Sequence

    from bytecode import Bytecode
    from bytecode import Instr

    from pynguin.instrumentation import StackEffects
    from pynguin.instrumentation.transformer import BranchCoverageInstrumentationAdapter
    from pynguin.instrumentation.transformer import (
        CheckedCoverageInstrumentationAdapter,
    )
    from pynguin.instrumentation.transformer import DynamicSeedingInstrumentationAdapter
    from pynguin.instrumentation.transformer import LineCoverageInstrumentationAdapter


__all__ = [
    "ACCESS_OPCODES",
    "CALL_OPCODES",
    "CLOSURE_LOAD_OPCODES",
    "COND_BRANCH_OPCODES",
    "IMPORT_FROM_OPCODES",
    "IMPORT_NAME_OPCODES",
    "LOAD_DEREF_OPCODES",
    "LOAD_FAST_OPCODES",
    "LOAD_GLOBAL_OPCODES",
    "LOAD_NAME_OPCODES",
    "MEMORY_DEF_OPCODES",
    "MEMORY_USE_OPCODES",
    "MODIFY_DEREF_OPCODES",
    "MODIFY_FAST_OPCODES",
    "MODIFY_GLOBAL_OPCODES",
    "MODIFY_NAME_OPCODES",
    "RETURNING_OPCODES",
    "STORE_NAME_OPCODES",
    "STORE_OPCODES",
    "TRACED_OPCODES",
    "YIELDING_OPCODES",
    "BranchCoverageInstrumentation",
    "CheckedCoverageInstrumentation",
    "DynamicSeedingInstrumentation",
    "LineCoverageInstrumentation",
    "add_for_loop_no_yield_nodes",
    "end_with_explicit_return_none",
    "get_branch_type",
    "is_conditional_jump",
    "stack_effects",
]


class StackEffectsFunction(Protocol):
    """A function that calculates the stack effects of an opcode."""

    @abstractmethod
    def __call__(self, opcode: int, arg: int | None, *, jump: bool = False) -> StackEffects:
        """Get the stack effects.

        The effects are represented as a tuple of number of pops and number of pushes
        for an opcode.

        Args:
            opcode: The opcode, to get the pops and pushes for.
            arg: numeric argument to operation (if any), otherwise None
            jump: if the code has a jump and jump is true

        Returns:
            A tuple containing the number of pops and pushes as integer.
        """


class IsConditionalJumpFunction(Protocol):
    """A function that checks if an opcode is a conditional jump."""

    @abstractmethod
    def __call__(self, instruction: Instr) -> bool:
        """Check if the instruction is a conditional jump.

        Args:
            instruction: The instruction to check.

        Returns:
            True if the instruction is a conditional jump, False otherwise.
        """


class AddForLoopNoYieldNodesFunction(Protocol):
    """A function that adds NOP nodes for for-loops that do not yield values.

    This can be used to instrument the for-loops that exit without using breaks or returns.

    Before:
    ```
         ├────────────┐
    ┌────▼────┐       │
    │FOR_ITER ├───┐   │
    └────┬────┘   │   │
         │     ┌──▼──┐│
         │     │BODY ├┘
         │     └──┬──┘
         ├──break─┘
      ┌──▼──┐
      │EXIT │
      └─────┘
    ```

    After:
    ```
         ├────────────┐
    ┌────▼────┐       │
    │FOR_ITER ├───┐   │
    └────┬────┘   │   │
       ┌─▼─┐   ┌──▼──┐│
       │NOP│   │BODY ├┘
       └─┬─┘   └──┬──┘
         ├──break─┘
      ┌──▼──┐
      │EXIT │
      └─────┘
    ```
    """

    @abstractmethod
    def __call__(self, bytecode: Bytecode) -> Bytecode:
        """Add NOP nodes for for-loops that do not yield values.

        Args:
            bytecode: The bytecode to modify.

        Returns:
            A new bytecode with NOP nodes added for for-loops that do not yield values.
        """


class GetBranchTypeFunction(Protocol):
    """A function that get the branch type of a conditional jump instruction."""

    @abstractmethod
    def __call__(self, opcode: int) -> bool | None:
        """Get the branch type of a conditional jump instruction.

        Args:
            opcode: The opcode of the instruction to check.

        Returns:
            The branch type as a boolean if it is a conditional jump instruction,
            or None if it is not a conditional jump instruction.
        """


class EndWithExplicitReturnNoneFunction(Protocol):
    """A function that checks if a sequence of instructions end with an explicit return None."""

    @abstractmethod
    def __call__(self, instructions: Sequence[Instr]) -> bool:
        """Check if the instructions end with an explicit return None.

        Args:
            instructions: The sequence of instructions to check.

        Returns:
            True if the instructions end with an explicit return None, False otherwise.
        """


stack_effects: StackEffectsFunction
is_conditional_jump: IsConditionalJumpFunction
add_for_loop_no_yield_nodes: AddForLoopNoYieldNodesFunction
get_branch_type: GetBranchTypeFunction
end_with_explicit_return_none: EndWithExplicitReturnNoneFunction

BranchCoverageInstrumentation: type[BranchCoverageInstrumentationAdapter]
LineCoverageInstrumentation: type[LineCoverageInstrumentationAdapter]
CheckedCoverageInstrumentation: type[CheckedCoverageInstrumentationAdapter]
DynamicSeedingInstrumentation: type[DynamicSeedingInstrumentationAdapter]

LOAD_FAST_OPCODES: tuple[int, ...]
MODIFY_FAST_OPCODES: tuple[int, ...]

LOAD_NAME_OPCODES: tuple[int, ...]
STORE_NAME_OPCODES: tuple[int, ...]
MODIFY_NAME_OPCODES: tuple[int, ...]

LOAD_GLOBAL_OPCODES: tuple[int, ...]
MODIFY_GLOBAL_OPCODES: tuple[int, ...]

LOAD_DEREF_OPCODES: tuple[int, ...]
MODIFY_DEREF_OPCODES: tuple[int, ...]

CLOSURE_LOAD_OPCODES: tuple[int, ...]

IMPORT_NAME_OPCODES: tuple[int, ...]
IMPORT_FROM_OPCODES: tuple[int, ...]

CALL_OPCODES: tuple[int, ...]
YIELDING_OPCODES: tuple[int, ...]
RETURNING_OPCODES: tuple[int, ...]
COND_BRANCH_OPCODES: tuple[int, ...]

STORE_OPCODES: tuple[int, ...]
ACCESS_OPCODES: tuple[int, ...]
TRACED_OPCODES: tuple[int, ...]
MEMORY_USE_OPCODES: tuple[int, ...]
MEMORY_DEF_OPCODES: tuple[int, ...]


if sys.version_info >= (3, 11):
    from .python3_11 import *  # noqa: F403
elif sys.version_info >= (3, 10):  # noqa: UP036
    from .python3_10 import *  # noqa: F403
else:
    raise ImportError(
        "This module requires Python 3.10 or higher. "
        "Please upgrade your Python version to use this feature."
    )
