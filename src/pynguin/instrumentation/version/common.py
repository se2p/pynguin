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
from typing import TYPE_CHECKING, Any, Protocol, TypeAlias

if TYPE_CHECKING:
    from bytecode.instr import _UNSET, Instr, InstrArg

    from pynguin.instrumentation import PynguinCompare
    from pynguin.instrumentation import controlflow as cf
    from pynguin.instrumentation.transformer import AstInfo


# Jump operations are the last operation within a basic block
JUMP_OP_POS = -1

# If a conditional jump is based on a comparison, it has to be the second-to-last
# instruction within the basic block.
COMPARE_OP_POS = -2


class InstrumentationSetupAction(enum.IntEnum):
    """An enum to represent what should done in the instrumentation setup."""

    NO_ACTION = enum.auto()
    """No action is performed."""

    COPY_FIRST = enum.auto()
    """The first element of the stack is copied."""

    COPY_FIRST_SHIFT_DOWN_TWO = enum.auto()
    """The first element of the stack is copied, and is shifted down two times."""

    COPY_SECOND = enum.auto()
    """The second element of the stack is copied."""

    COPY_SECOND_SHIFT_DOWN_TWO = enum.auto()
    """The second element of the stack is copied, and is shifted down two times."""

    COPY_SECOND_SHIFT_DOWN_THREE = enum.auto()
    """The second element of the stack is copied, and is shifted down three times."""

    COPY_THIRD_SHIFT_DOWN_THREE = enum.auto()
    """The third element of the stack is copied, and is shifted down three times."""

    COPY_THIRD_SHIFT_DOWN_FOUR = enum.auto()
    """The third element of the stack is copied, and is shifted down four times."""

    COPY_FIRST_TWO = enum.auto()
    """The first two elements of the stack are copied."""

    ADD_FIRST_TWO = enum.auto()
    """The first two elements of the stack are added."""

    ADD_FIRST_TWO_REVERSED = enum.auto()
    """The first two elements of the stack are reversed then added."""


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
class InstrumentationFastLoadTuple:
    """Represents two fast loads stored in a tuple and used in instrumentation."""

    names: tuple[str, str]


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


InstrumentationArgument: TypeAlias = (
    InstrumentationConstantLoad
    | InstrumentationFastLoad
    | InstrumentationFastLoadTuple
    | InstrumentationNameLoad
    | InstrumentationGlobalLoad
    | InstrumentationStackValue
    | InstrumentationDeref
    | InstrumentationClassDeref
)


class InstrumentationInstructionsGenerator(Protocol):
    """Represents a class that generates instructions for instrumentation."""

    @classmethod
    @abstractmethod
    def generate_setup_instructions(
        cls,
        setup_action: InstrumentationSetupAction,
        lineno: int | _UNSET | None,
    ) -> tuple[cf.ArtificialInstr, ...]:
        """Generate setup instructions for instrumentation.

        It is recommended to directly use the `generate_overriding_instructions` or
        `generate_instructions` methods when possible to avoid mistakes.

        Args:
            setup_action: The action to perform in the setup.
            lineno: The line number for the instruction.

        Returns:
            A tuple of artificial instructions that perform the setup.
        """

    @classmethod
    @abstractmethod
    def generate_method_call_instructions(
        cls,
        method_call: InstrumentationMethodCall,
        lineno: int | _UNSET | None,
    ) -> tuple[cf.ArtificialInstr, ...]:
        """Generate instructions for a method call in instrumentation.

        It is recommended to directly use the `generate_overriding_instructions` or
        `generate_instructions` methods when possible to avoid mistakes.

        Args:
            method_call: The method call to perform.
            lineno: The line number for the instruction.

        Returns:
            A tuple of artificial instructions that perform the method call.
        """

    @classmethod
    @abstractmethod
    def generate_teardown_instructions(
        cls,
        setup_action: InstrumentationSetupAction,
        lineno: int | _UNSET | None,
    ) -> tuple[cf.ArtificialInstr, ...]:
        """Generate teardown instructions for instrumentation.

        It is recommended to directly use the `generate_overriding_instructions` or
        `generate_instructions` methods when possible to avoid mistakes.

        Args:
            setup_action: The action that was performed in the setup.
            lineno: The line number for the instruction.

        Returns:
            A tuple of artificial instructions that perform the teardown.
        """

    @classmethod
    def generate_instructions(
        cls,
        setup_action: InstrumentationSetupAction,
        instrumentation_method_call: InstrumentationMethodCall,
        lineno: int | _UNSET | None,
    ) -> tuple[cf.ArtificialInstr, ...]:
        """Generate instructions for instrumentation.

        Args:
            setup_action: The action to perform in the setup.
            instrumentation_method_call: The method call to convert.
            lineno: The line number for the instruction.

        Returns:
            A tuple of artificial instructions representing the instrumentation.
        """
        return (
            *cls.generate_setup_instructions(setup_action, lineno),
            *cls.generate_method_call_instructions(instrumentation_method_call, lineno),
            *cls.generate_teardown_instructions(setup_action, lineno),
        )

    @classmethod
    def generate_overriding_instructions(
        cls,
        setup_action: InstrumentationSetupAction,
        instr: Instr,
        instrumentation_method_call: InstrumentationMethodCall,
        lineno: int | _UNSET | None,
    ) -> tuple[cf.Instr, ...]:
        """Generate instructions for overriding a existing instruction.

        Args:
            setup_action: The action to perform in the setup.
            instr: The instruction to override.
            instrumentation_method_call: The method call to convert.
            lineno: The line number for the instruction.

        Returns:
            A tuple of instructions that override the existing instruction.
        """
        return (
            *cls.generate_setup_instructions(setup_action, lineno),
            instr,
            *cls.generate_method_call_instructions(instrumentation_method_call, lineno),
            *cls.generate_teardown_instructions(setup_action, lineno),
        )


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


class CheckedCoverageInstrumentationVisitorMethod(Protocol):
    """Represents a visitor method used in checked coverage instrumentation."""

    @abstractmethod
    def __call__(  # noqa: PLR0917
        _self,  # noqa: N805
        self,
        ast_info: AstInfo | None,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
        instr_original_index: int,
    ) -> None:
        """Visit an instruction in the control flow graph.

        Args:
            self: The instance of the checked coverage instrumentation.
            ast_info: The AST info, if it exists.
            cfg: The control flow graph.
            code_object_id: The code object id of the containing code object.
            node: The node in the control flow graph.
            instr: The instruction being visited.
            instr_index: The index of the instruction in the basic block.
            instr_original_index: The original index of the instruction in the code object.
        """


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


def extract_name(arg: InstrArg) -> str | None:
    """Extract the name from an instruction argument.

    Starting with Python 3.11, some instructions use a tuple as argument. However, we
    sometimes just need the name part of the argument. This function handles both cases.
    If the argument is a str, it returns it directly. If it is a tuple, it returns the
    second element of the tuple, which is expected to be the name.

    Args:
        arg: The argument from which to extract the name.

    Returns:
        The name extracted from the instruction, or None if the argument is not a string or tuple.
    """
    match arg:
        case str(name):
            return name
        case (bool(), str(name)):
            return name
        case _:
            return None
