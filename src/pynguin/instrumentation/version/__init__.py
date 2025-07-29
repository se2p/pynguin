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

    from pynguin.instrumentation import StackEffect
    from pynguin.instrumentation.transformer import BranchCoverageInstrumentationAdapter
    from pynguin.instrumentation.transformer import (
        CheckedCoverageInstrumentationAdapter,
    )
    from pynguin.instrumentation.transformer import DynamicSeedingInstrumentationAdapter
    from pynguin.instrumentation.transformer import LineCoverageInstrumentationAdapter


class StackEffectFunction(Protocol):
    """A function that calculates the stack effect of an opcode."""

    @abstractmethod
    def __call__(self, opcode: int, arg: int | None, *, jump: bool = False) -> StackEffect:
        """Get the stack effect.

        The effect is represented as a tuple of number of pops and number of pushes
        for an opcode.

        Args:
            opcode: The opcode, to get the pops and pushes for.
            arg: numeric argument to operation (if any), otherwise None
            jump: if the code has a jump and jump is true

        Returns:
            A tuple containing the number of pops and pushes as integer.
        """


class IsYieldingFunction(Protocol):
    """A function that checks if an instruction is yielding."""

    @abstractmethod
    def __call__(self, opcode: int) -> bool:
        """Check if the instruction is yielding.

        Args:
            opcode: The opcode of the instruction to check.

        Returns:
            True if the instruction is yielding, False otherwise.
        """


class IsForLoopFunction(Protocol):
    """A function that checks if an instruction is a for loop."""

    @abstractmethod
    def __call__(self, opcode: int) -> bool:
        """Check if the instruction is a for loop.

        Args:
            opcode: The opcode of the instruction to check.

        Returns:
            True if the instruction is a for loop, False otherwise.
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


class IsImportFunction(Protocol):
    """A function that checks if an instruction is an import statement."""

    @abstractmethod
    def __call__(self, opcode: int) -> bool:
        """Check if the instruction is an import statement.

        Args:
            opcode: The opcode of the instruction to check.

        Returns:
            True if the instruction is an import statement, False otherwise.
        """


class GetBooleanConditionFunction(Protocol):
    """A function that get the boolean value required on the ToS to jump to the instr args."""

    @abstractmethod
    def __call__(self, opcode: int) -> bool | None:
        """Get the boolean value required on the ToS to jump to the instr args.

        Args:
            opcode: The opcode of the instruction to check.

        Returns:
            The boolean value required on the ToS to jump to the instr args,
            or None if the instruction is not a conditional jump or a for loop.
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


class IsStoreNameFunction(Protocol):
    """A function that checks if an instruction stores a name."""

    @abstractmethod
    def __call__(self, opcode: int) -> bool:
        """Check if the instruction stores a name.

        Args:
            opcode: The opcode of the instruction to check.

        Returns:
            True if the instruction stores a name, False otherwise.
        """


stack_effect: StackEffectFunction
is_yielding: IsYieldingFunction
is_import: IsImportFunction
is_for_loop: IsForLoopFunction
add_for_loop_no_yield_nodes: AddForLoopNoYieldNodesFunction
get_boolean_condition: GetBooleanConditionFunction
end_with_explicit_return_none: EndWithExplicitReturnNoneFunction
BranchCoverageInstrumentation: type[BranchCoverageInstrumentationAdapter]
LineCoverageInstrumentation: type[LineCoverageInstrumentationAdapter]
CheckedCoverageInstrumentation: type[CheckedCoverageInstrumentationAdapter]
DynamicSeedingInstrumentation: type[DynamicSeedingInstrumentationAdapter]
TRACED_INSTRUCTIONS: tuple[int, ...]
MEMORY_DEF_INSTRUCTIONS: tuple[int, ...]
MEMORY_USE_INSTRUCTIONS: tuple[int, ...]
COND_BRANCH_INSTRUCTIONS: tuple[int, ...]
OP_EXTENDED_ARG: tuple[int, ...]
OP_LOCAL_LOAD: tuple[int, ...]
OP_LOCAL_MODIFY: tuple[int, ...]
OP_NAME_LOAD: tuple[int, ...]
OP_NAME_MODIFY: tuple[int, ...]
OP_GLOBAL_LOAD: tuple[int, ...]
OP_GLOBAL_MODIFY: tuple[int, ...]
OP_DEREF_LOAD: tuple[int, ...]
OP_DEREF_MODIFY: tuple[int, ...]
OP_CLOSURE_LOAD: tuple[int, ...]
OP_IMPORT_FROM: tuple[int, ...]
OP_RETURN: tuple[int, ...]
OP_STORES: tuple[int, ...]
OP_ACCESS: tuple[int, ...]
OP_STORE_NAME: tuple[int, ...]

if sys.version_info >= (3, 10):  # noqa: UP036
    from .python3_10 import *  # noqa: F403
else:
    raise ImportError(
        "This module requires Python 3.10 or higher. "
        "Please upgrade your Python version to use this feature."
    )
