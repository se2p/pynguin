#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#

# Idea and structure are taken from the pyChecco project, see:
# https://github.com/ipsw1/pychecco

"""Provides version-specific functions for Python 3.10."""

from __future__ import annotations

import logging
from opcode import opname
from opcode import stack_effect as opcode_stack_effect
from typing import TYPE_CHECKING, ClassVar

from bytecode.cfg import BasicBlock
from bytecode.instr import _UNSET, UNSET, Compare, Instr, Label

from pynguin.analyses.constants import DynamicConstantProvider
from pynguin.instrumentation import AST_FILENAME, PynguinCompare, StackEffects, tracer, transformer
from pynguin.instrumentation import controlflow as cf
from pynguin.instrumentation.version.common import (
    COMPARE_OP_POS,
    JUMP_OP_POS,
    CheckedCoverageInstrumentationVisitorMethod,
    ExtractComparisonFunction,
    InstrumentationArgument,
    InstrumentationClassDeref,
    InstrumentationConstantLoad,
    InstrumentationDeref,
    InstrumentationFastLoad,
    InstrumentationFastLoadTuple,
    InstrumentationGlobalLoad,
    InstrumentationInstructionsGenerator,
    InstrumentationMethodCall,
    InstrumentationNameLoad,
    InstrumentationSetupAction,
    InstrumentationStackValue,
    after,
    before,
    extract_name,
    override,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from bytecode import Bytecode

__all__ = [
    "ACCESS_NAMES",
    "CALL_NAMES",
    "CLOSURE_LOAD_NAMES",
    "COND_BRANCH_NAMES",
    "IMPORT_FROM_NAMES",
    "IMPORT_NAME_NAMES",
    "LOAD_DEREF_NAMES",
    "LOAD_FAST_NAMES",
    "LOAD_GLOBAL_NAMES",
    "LOAD_NAME_NAMES",
    "MEMORY_DEF_NAMES",
    "MEMORY_USE_NAMES",
    "MODIFY_DEREF_NAMES",
    "MODIFY_FAST_NAMES",
    "MODIFY_GLOBAL_NAMES",
    "MODIFY_NAME_NAMES",
    "RETURNING_NAMES",
    "RETURN_NONE_SIZE",
    "STORE_NAMES",
    "STORE_NAME_NAMES",
    "TRACED_NAMES",
    "YIELDING_NAMES",
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

# Fast opcodes
LOAD_FAST_NAMES = ("LOAD_FAST",)
MODIFY_FAST_NAMES = (
    "STORE_FAST",
    "DELETE_FAST",
)
ACCESS_FAST_NAMES = LOAD_FAST_NAMES + MODIFY_FAST_NAMES


# Name opcodes
LOAD_NAME_NAMES = ("LOAD_NAME",)
STORE_NAME_NAMES = ("STORE_NAME",)
MODIFY_NAME_NAMES = (
    *STORE_NAME_NAMES,
    "DELETE_NAME",
)
ACCESS_NAME_NAMES = LOAD_NAME_NAMES + MODIFY_NAME_NAMES


# Global opcodes
LOAD_GLOBAL_NAMES = ("LOAD_GLOBAL",)
MODIFY_GLOBAL_NAMES = (
    "STORE_GLOBAL",
    "DELETE_GLOBAL",
)
ACCESS_GLOBAL_NAMES = LOAD_GLOBAL_NAMES + MODIFY_GLOBAL_NAMES


# Deref opcodes
LOAD_DEREF_NAMES = (
    "LOAD_DEREF",
    "LOAD_CLASSDEREF",
)
MODIFY_DEREF_NAMES = (
    "STORE_DEREF",
    "DELETE_DEREF",
)
ACCESS_DEREF_NAMES = LOAD_DEREF_NAMES + MODIFY_DEREF_NAMES


# Closure opcodes
CLOSURE_LOAD_NAMES = ("LOAD_CLOSURE",)


# Import opcodes
IMPORT_NAME_NAMES = ("IMPORT_NAME",)
IMPORT_FROM_NAMES = ("IMPORT_FROM",)


# Attr opcodes
LOAD_ATTR_NAMES = ("LOAD_ATTR",)
STORE_ATTR_NAMES = ("STORE_ATTR",)
DELETE_ATTR_NAMES = ("DELETE_ATTR",)
MODIFY_ATTR_NAMES = STORE_ATTR_NAMES + DELETE_ATTR_NAMES
ACCESS_ATTR_NAMES = LOAD_ATTR_NAMES + MODIFY_ATTR_NAMES


# Subscr opcodes
STORE_SUBSCR_NAMES = ("STORE_SUBSCR",)
BINARY_SUBSCR_NAMES = ("BINARY_SUBSCR",)
ACCESS_SUBSCR_NAMES = STORE_SUBSCR_NAMES + BINARY_SUBSCR_NAMES + ("DELETE_SUBSCR",)


# Remaining opcodes
LOAD_METHOD_NAMES = ("LOAD_METHOD",)

EXTENDED_ARG_NAMES = ("EXTENDED_ARG",)

CALL_NAMES = (
    "CALL_FUNCTION",
    "CALL_FUNCTION_KW",
    "CALL_FUNCTION_EX",
    "CALL_METHOD",
    "YIELD_FROM",
)

YIELDING_NAMES = (
    "YIELD_VALUE",
    "YIELD_FROM",
)

RETURNING_NAMES = ("RETURN_VALUE", "YIELD_VALUE")

COMPARE_NAMES = (
    "COMPARE_OP",
    "IS_OP",
    "CONTAINS_OP",
)

OPERATION_NAMES = (
    *COMPARE_NAMES,
    # Unary operations
    "UNARY_POSITIVE",
    "UNARY_NEGATIVE",
    "UNARY_NOT",
    "UNARY_INVERT",
    "GET_ITER",
    "GET_YIELD_FROM_ITER",
    # Binary operations
    "BINARY_POWER",
    "BINARY_MULTIPLY",
    "BINARY_MATRIX_MULTIPLY",
    "BINARY_FLOOR_DIVIDE",
    "BINARY_TRUE_DIVIDE",
    "BINARY_MODULO",
    "BINARY_ADD",
    "BINARY_SUBTRACT",
    "BINARY_LSHIFT",
    "BINARY_RSHIFT",
    "BINARY_AND",
    "BINARY_XOR",
    "BINARY_OR",
    # In-place operations
    "INPLACE_POWER",
    "INPLACE_MULTIPLY",
    "INPLACE_MATRIX_MULTIPLY",
    "INPLACE_FLOOR_DIVIDE",
    "INPLACE_TRUE_DIVIDE",
    "INPLACE_MODULO",
    "INPLACE_ADD",
    "INPLACE_SUBTRACT",
    "INPLACE_LSHIFT",
    "INPLACE_RSHIFT",
    "INPLACE_AND",
    "INPLACE_XOR",
    "INPLACE_OR",
)

COND_BRANCH_NAMES = (
    "POP_JUMP_IF_TRUE",
    "POP_JUMP_IF_FALSE",
    "JUMP_IF_TRUE_OR_POP",
    "JUMP_IF_FALSE_OR_POP",
    "JUMP_IF_NOT_EXC_MATCH",
    "FOR_ITER",
)

JUMP_NAMES = (
    *COND_BRANCH_NAMES,
    "JUMP_ABSOLUTE",
    "JUMP_FORWARD",
    "SETUP_FINALLY",
    "SETUP_WITH",
    "SETUP_ASYNC_WITH",
)


# Regrouping opcodes
STORE_NAMES = STORE_SUBSCR_NAMES + STORE_ATTR_NAMES

ACCESS_NAMES = IMPORT_FROM_NAMES + LOAD_ATTR_NAMES + DELETE_ATTR_NAMES

ATTRIBUTES_NAMES = IMPORT_FROM_NAMES + ACCESS_ATTR_NAMES + LOAD_METHOD_NAMES

TRACED_NAMES = (
    OPERATION_NAMES
    + ACCESS_FAST_NAMES
    + ACCESS_NAME_NAMES
    + ACCESS_GLOBAL_NAMES
    + ACCESS_DEREF_NAMES
    + ATTRIBUTES_NAMES
    + ACCESS_SUBSCR_NAMES
    + IMPORT_NAME_NAMES
    + JUMP_NAMES
    + CALL_NAMES
    + RETURNING_NAMES
)

MEMORY_USE_NAMES = (
    LOAD_FAST_NAMES
    + LOAD_NAME_NAMES
    + LOAD_GLOBAL_NAMES
    + LOAD_DEREF_NAMES
    + LOAD_ATTR_NAMES
    + IMPORT_FROM_NAMES
    + LOAD_METHOD_NAMES
    + CLOSURE_LOAD_NAMES
    + BINARY_SUBSCR_NAMES
)
MEMORY_DEF_NAMES = (
    MODIFY_FAST_NAMES
    + MODIFY_NAME_NAMES
    + MODIFY_GLOBAL_NAMES
    + MODIFY_DEREF_NAMES
    + MODIFY_ATTR_NAMES
    + IMPORT_NAME_NAMES  # compensate incorrect stack effect for IMPORT_NAME
    + ACCESS_SUBSCR_NAMES
)

RETURN_NONE_SIZE: int = 2


def is_conditional_jump(instruction: Instr) -> bool:  # noqa: D103
    return instruction.is_cond_jump() or instruction.name == "FOR_ITER"


def add_for_loop_no_yield_nodes(bytecode: Bytecode) -> Bytecode:  # noqa: D103
    bytecode_copy = bytecode.copy()
    i = 0
    while i < len(bytecode_copy):
        instruction = bytecode_copy[i]

        if (
            isinstance(instruction, Instr)
            and instruction.name == "FOR_ITER"
            and isinstance(instruction.arg, Label)
        ):
            exit_label = instruction.arg

            exit_label_index = bytecode_copy.index(exit_label)

            dummy_label = Label()

            bytecode_copy[exit_label_index:exit_label_index] = [
                dummy_label,
                Instr(
                    "NOP",
                    lineno=instruction.lineno,
                    location=instruction.location,
                ),
            ]

            instruction.arg = dummy_label

        i += 1

    return bytecode_copy


def get_branch_type(opcode: int) -> bool | None:  # noqa: D103
    match opname[opcode]:
        case "POP_JUMP_IF_TRUE" | "JUMP_IF_TRUE_OR_POP":
            # These jump to arg if ToS is True
            return True
        case "POP_JUMP_IF_FALSE" | "JUMP_IF_FALSE_OR_POP" | "JUMP_IF_NOT_EXC_MATCH" | "FOR_ITER":
            # These jump to arg if ToS is False, is Empty or if Exc does not
            # match.
            return False
        case _:
            # Not a conditional jump or a for loop instruction
            return None


def end_with_explicit_return_none(instructions: Sequence[Instr]) -> bool:  # noqa: D103
    return (
        len(instructions) >= 3
        # check if the "return None" is implicit or explicit
        and instructions[-3].lineno != instructions[-2].lineno
        and instructions[-2].name == "LOAD_CONST"
        and instructions[-2].arg is None
        and instructions[-1].name == "RETURN_VALUE"
    )


def stack_effects(  # noqa: D103, C901, PLR0915
    opcode: int,
    arg: int | None,
    *,
    jump: bool = False,
) -> StackEffects:
    match opname[opcode]:
        case (
            "NOP"
            | "SETUP_ANNOTATIONS"
            | "POP_BLOCK"
            | "DELETE_NAME"
            | "DELETE_GLOBAL"
            | "JUMP_FORWARD"
            | "JUMP_ABSOLUTE"
            | "DELETE_FAST"
            | "DELETE_DEREF"
            | "EXTENDED_ARG"
            | "ROT_N"
        ):
            return StackEffects(0, 0)
        case (
            "POP_TOP"
            | "PRINT_EXPR"
            | "RETURN_VALUE"
            | "STORE_NAME"
            | "IMPORT_STAR"
            | "DELETE_ATTR"
            | "STORE_GLOBAL"
            | "POP_JUMP_IF_FALSE"
            | "POP_JUMP_IF_TRUE"
            | "STORE_FAST"
            | "STORE_DEREF"
            | "LIST_APPEND"
            | "SET_ADD"
            | "GEN_START"
        ):
            return StackEffects(1, 0)
        case "DELETE_SUBSCR" | "STORE_ATTR" | "MAP_ADD" | "JUMP_IF_NOT_EXC_MATCH":
            return StackEffects(2, 0)
        case "STORE_SUBSCR" | "POP_EXCEPT" | "RERAISE":
            return StackEffects(3, 0)
        case "END_ASYNC_FOR":
            return StackEffects(7, 0)
        case (
            "LOAD_BUILD_CLASS"
            | "LOAD_CONST"
            | "LOAD_NAME"
            | "IMPORT_FROM"
            | "LOAD_GLOBAL"
            | "LOAD_FAST"
            | "LOAD_CLOSURE"
            | "LOAD_DEREF"
            | "LOAD_CLASSDEREF"
            | "WITH_EXCEPT_START"
            | "LOAD_ASSERTION_ERROR"
            | "GET_LEN"
            | "MATCH_MAPPING"
            | "MATCH_SEQUENCE"
        ):
            return StackEffects(0, 1)
        case "MATCH_KEYS":
            return StackEffects(0, 2)
        case (
            "UNARY_POSITIVE"
            | "UNARY_NEGATIVE"
            | "UNARY_NOT"
            | "UNARY_INVERT"
            | "GET_AITER"
            | "GET_ITER"
            | "GET_YIELD_FROM_ITER"
            | "GET_AWAITABLE"
            | "GET_AWAITABLE"
            | "YIELD_VALUE"
            | "LOAD_ATTR"
            | "LIST_TO_TUPLE"
        ):
            return StackEffects(1, 1)
        case "ROT_TWO" | "COPY_DICT_WITHOUT_KEYS":
            return StackEffects(2, 2)
        case "ROT_THREE":
            return StackEffects(3, 3)
        case "ROT_FOUR":
            return StackEffects(4, 4)
        case "DUP_TOP" | "BEFORE_ASYNC_WITH" | "GET_ANEXT" | "LOAD_METHOD":
            return StackEffects(1, 2)
        case (
            "BINARY_MATRIX_MULTIPLY"
            | "INPLACE_MATRIX_MULTIPLY"
            | "BINARY_POWER"
            | "BINARY_MULTIPLY"
            | "BINARY_MODULO"
            | "BINARY_ADD"
            | "BINARY_SUBTRACT"
            | "BINARY_SUBSCR"
            | "BINARY_FLOOR_DIVIDE"
            | "BINARY_TRUE_DIVIDE"
            | "INPLACE_FLOOR_DIVIDE"
            | "INPLACE_TRUE_DIVIDE"
            | "INPLACE_ADD"
            | "INPLACE_SUBTRACT"
            | "INPLACE_MULTIPLY"
            | "INPLACE_MODULO"
            | "BINARY_LSHIFT"
            | "BINARY_RSHIFT"
            | "BINARY_AND"
            | "BINARY_XOR"
            | "BINARY_OR"
            | "INPLACE_POWER"
            | "YIELD_FROM"
            | "INPLACE_LSHIFT"
            | "INPLACE_RSHIFT"
            | "INPLACE_AND"
            | "INPLACE_XOR"
            | "INPLACE_OR"
            | "COMPARE_OP"
            | "IMPORT_NAME"
            | "IS_OP"
            | "CONTAINS_OP"
            | "MATCH_CLASS"
            | "LIST_EXTEND"
            | "SET_UPDATE"
            | "DICT_MERGE"
            | "DICT_UPDATE"
        ):
            return StackEffects(2, 1)
        case "DUP_TOP_TWO":
            return StackEffects(2, 4)
        # jump based operations
        case "SETUP_WITH":
            return StackEffects(0, 6) if jump else StackEffects(0, 1)
        case "FOR_ITER":
            return StackEffects(1, 0) if jump else StackEffects(1, 2)
        case "JUMP_IF_TRUE_OR_POP" | "JUMP_IF_FALSE_OR_POP":
            return StackEffects(0, 0) if jump else StackEffects(1, 0)
        case "SETUP_ASYNC_WITH":
            return StackEffects(0, 5) if jump else StackEffects(0, 0)
        case "SETUP_FINALLY":
            return StackEffects(0, 6) if jump else StackEffects(0, 0)
        # argument dependant operations
        case "UNPACK_SEQUENCE":
            assert arg is not None
            return StackEffects(1, arg)
        case "UNPACK_EX":
            assert arg is not None
            return StackEffects(1, (arg & 0xFF) + (arg >> 8) + 1)
        case "BUILD_TUPLE" | "BUILD_LIST" | "BUILD_SET" | "BUILD_STRING":
            assert arg is not None
            return StackEffects(arg, 1)
        case "BUILD_MAP":
            assert arg is not None
            return StackEffects(2 * arg, 1)
        case "BUILD_CONST_KEY_MAP" | "CALL_FUNCTION":
            assert arg is not None
            return StackEffects(1 + arg, 1)
        case "RAISE_VARARGS":
            assert arg is not None
            return StackEffects(arg, 0)
        case "CALL_METHOD" | "CALL_FUNCTION_KW":
            assert arg is not None
            return StackEffects(2 + arg, 1)
        case "CALL_FUNCTION_EX":
            assert arg is not None
            # argument contains flags
            pops = 2
            if arg & 0x01 != 0:
                pops += 1
            return StackEffects(pops, 1)
        case "MAKE_FUNCTION":
            assert arg is not None
            # argument contains flags
            pops = 2
            if arg & 0x01 != 0:
                pops += 1
            if arg & 0x02 != 0:
                pops += 1
            if arg & 0x04 != 0:
                pops += 1
            if arg & 0x08 != 0:
                pops += 1
            return StackEffects(pops, 1)
        case "FORMAT_VALUE":
            assert arg is not None
            # argument contains flags
            pops = 0
            if arg & 0x03 in {0, 1, 2, 3}:
                pops += 1
            if arg & 0x04 == 4:
                pops += 1
            return StackEffects(pops, 1)
        case "BUILD_SLICE":
            return StackEffects(3, 1) if arg == 3 else StackEffects(2, 1)
        case _:
            try:
                stack_effect = opcode_stack_effect(opcode, arg, jump=jump)
            except ValueError:
                # If an argument is used for an opcode that does not support it,
                # it raises a ValueError.
                stack_effect = None

            raise AssertionError(
                f"The opcode {opcode} (name={opname[opcode]}, arg={arg}, jump={jump}, "
                f"stack_effect={stack_effect}) isn't recognized."
            )


class Python310InstrumentationInstructionsGenerator(InstrumentationInstructionsGenerator):
    """Generates instrumentation instructions for Python 3.10."""

    @classmethod
    def generate_setup_instructions(  # noqa: C901
        cls,
        setup_action: InstrumentationSetupAction,
        lineno: int | _UNSET | None,
    ) -> tuple[cf.ArtificialInstr, ...]:
        match setup_action:
            case InstrumentationSetupAction.NO_ACTION:
                return ()
            case InstrumentationSetupAction.COPY_FIRST:
                return (cf.ArtificialInstr("DUP_TOP", lineno=lineno),)
            case InstrumentationSetupAction.COPY_FIRST_SHIFT_DOWN_TWO:
                return (
                    cf.ArtificialInstr("DUP_TOP", lineno=lineno),
                    cf.ArtificialInstr("ROT_THREE", lineno=lineno),
                )
            case InstrumentationSetupAction.COPY_SECOND:
                return (
                    cf.ArtificialInstr("DUP_TOP_TWO", lineno=lineno),
                    cf.ArtificialInstr("POP_TOP", lineno=lineno),
                )
            case InstrumentationSetupAction.COPY_SECOND_SHIFT_DOWN_TWO:
                return (
                    cf.ArtificialInstr("ROT_TWO", lineno=lineno),
                    cf.ArtificialInstr("DUP_TOP", lineno=lineno),
                    cf.ArtificialInstr("ROT_THREE", lineno=lineno),
                    cf.ArtificialInstr("ROT_THREE", lineno=lineno),
                )
            case InstrumentationSetupAction.COPY_SECOND_SHIFT_DOWN_THREE:
                return (
                    cf.ArtificialInstr("ROT_TWO", lineno=lineno),
                    cf.ArtificialInstr("DUP_TOP", lineno=lineno),
                    cf.ArtificialInstr("ROT_FOUR", lineno=lineno),
                    cf.ArtificialInstr("ROT_TWO", lineno=lineno),
                )
            case InstrumentationSetupAction.COPY_THIRD_SHIFT_DOWN_THREE:
                return (
                    cf.ArtificialInstr("ROT_THREE", lineno=lineno),
                    cf.ArtificialInstr("ROT_THREE", lineno=lineno),
                    cf.ArtificialInstr("DUP_TOP", lineno=lineno),
                    cf.ArtificialInstr("ROT_FOUR", lineno=lineno),
                    cf.ArtificialInstr("ROT_FOUR", lineno=lineno),
                )
            case InstrumentationSetupAction.COPY_THIRD_SHIFT_DOWN_FOUR:
                raise ValueError("COPY_THIRD_SHIFT_DOWN_FOUR cannot be implemented in Python 3.10")
            case InstrumentationSetupAction.COPY_FIRST_TWO:
                return (cf.ArtificialInstr("DUP_TOP_TWO", lineno=lineno),)
            case InstrumentationSetupAction.ADD_FIRST_TWO:
                return (
                    cf.ArtificialInstr("DUP_TOP_TWO", lineno=lineno),
                    cf.ArtificialInstr("BINARY_ADD", lineno=lineno),
                )
            case InstrumentationSetupAction.ADD_FIRST_TWO_REVERSED:
                return (
                    cf.ArtificialInstr("DUP_TOP_TWO", lineno=lineno),
                    cf.ArtificialInstr("ROT_TWO", lineno=lineno),
                    cf.ArtificialInstr("BINARY_ADD", lineno=lineno),
                )
            case _:
                raise ValueError(f"Unsupported instrumentation setup action: {setup_action}.")

    @classmethod
    def _generate_argument_instructions(
        cls,
        arg: InstrumentationArgument,
        position: int,  # noqa: ARG003
        lineno: int | _UNSET | None,
    ) -> tuple[cf.ArtificialInstr, ...]:
        match arg:
            case InstrumentationConstantLoad(value):
                return (cf.ArtificialInstr("LOAD_CONST", value, lineno=lineno),)  # type: ignore[arg-type]
            case InstrumentationFastLoad(name):
                return (cf.ArtificialInstr("LOAD_FAST", name, lineno=lineno),)
            case InstrumentationFastLoadTuple(names):
                return (
                    cf.ArtificialInstr("LOAD_FAST", names[0], lineno=lineno),
                    cf.ArtificialInstr("LOAD_FAST", names[1], lineno=lineno),
                    cf.ArtificialInstr("BUILD_TUPLE", 2, lineno=lineno),
                )
            case InstrumentationNameLoad(name):
                return (cf.ArtificialInstr("LOAD_NAME", name, lineno=lineno),)
            case InstrumentationGlobalLoad(name):
                return (cf.ArtificialInstr("LOAD_GLOBAL", name, lineno=lineno),)
            case InstrumentationDeref(name):
                return (cf.ArtificialInstr("LOAD_DEREF", name, lineno=lineno),)
            case InstrumentationClassDeref(name):
                return (cf.ArtificialInstr("LOAD_CLASSDEREF", name, lineno=lineno),)
            case InstrumentationStackValue():
                raise ValueError(
                    "There cannot be multiple stack arguments targeting the same positions"
                )

    @classmethod
    def generate_method_call_instructions(  # noqa: C901, PLR0915
        cls,
        method_call: InstrumentationMethodCall,
        lineno: int | _UNSET | None,
    ) -> tuple[cf.ArtificialInstr, ...]:
        try:
            first_index = method_call.args.index(InstrumentationStackValue.FIRST)
        except ValueError:
            first_index = None

        try:
            second_index = method_call.args.index(InstrumentationStackValue.SECOND)
        except ValueError:
            second_index = None

        move_stack_arguments_up: tuple[cf.ArtificialInstr, ...]
        match (first_index is not None, second_index is not None):
            case (False, False):
                move_stack_arguments_up = ()
            case (True, False):
                # The first stack argument is present but the second is not,
                # so we need to move it after the LOAD_METHOD instruction while
                # keeping the second stack argument at its original position.
                move_stack_arguments_up = (
                    cf.ArtificialInstr("ROT_THREE", lineno=lineno),
                    cf.ArtificialInstr("ROT_THREE", lineno=lineno),
                )
            case (False, True):
                # The second stack argument is present but the first is not,
                # so we need to move it after the LOAD_METHOD instruction while
                # keeping the first stack argument at its original position.
                move_stack_arguments_up = (
                    cf.ArtificialInstr("ROT_FOUR", lineno=lineno),
                    cf.ArtificialInstr("ROT_FOUR", lineno=lineno),
                    cf.ArtificialInstr("ROT_FOUR", lineno=lineno),
                )
            case (True, True):
                # Both stack arguments are present, so we need to move them
                # after the LOAD_METHOD instruction.
                move_stack_arguments_up = (
                    cf.ArtificialInstr("ROT_FOUR", lineno=lineno),
                    cf.ArtificialInstr("ROT_FOUR", lineno=lineno),
                )

        target_positions: list[int]
        swap_stack_arguments: tuple[cf.ArtificialInstr, ...]
        match (first_index, second_index):
            case (None, None):
                # No stack arguments, so don't need to swap or move anything.
                swap_stack_arguments = ()
                target_positions = []
            case (None, second_position):
                assert isinstance(second_position, int)
                # Only the second stack argument is present, so we need to target it.
                swap_stack_arguments = ()
                target_positions = [second_position]
            case (first_position, None):
                assert isinstance(first_position, int)
                # Only the first stack argument is present, so we need to target it.
                swap_stack_arguments = ()
                target_positions = [first_position]
            case (first_position, second_position):
                assert isinstance(first_position, int)
                assert isinstance(second_position, int)
                if first_position < second_position:
                    # Both stack arguments are present, and the order in which they appear
                    # in the stack is different from the order in which they appear in the
                    # args tuple, so we need to swap them and target both.
                    swap_stack_arguments = (cf.ArtificialInstr("ROT_TWO", lineno=lineno),)
                    target_positions = [first_position, second_position]
                else:
                    # Both stack arguments are present, and the order in which they appear
                    # in the stack is the same as in the args tuple, so we don't need to swap
                    # them, but we still need to target both.
                    swap_stack_arguments = ()
                    target_positions = [second_position, first_position]

        arguments_instructions: list[cf.ArtificialInstr] = []
        for position, arg in enumerate(method_call.args):
            if target_positions and position == target_positions[0]:
                # We are at the position of a targeted stack argument, so we just need
                # to keep the value on the stack at this position and remove the target.
                target_positions.pop(0)
                continue

            # We add the instructions to load the value onto the stack.
            arguments_instructions.extend(
                cls._generate_argument_instructions(arg, position, lineno)
            )

            match len(target_positions):
                case 0:
                    # No more targeted stack arguments, so do not have to swap anything.
                    pass
                case 1:
                    # There is only one target so we need to move the remaining stack argument
                    # above the value that we just loaded.
                    arguments_instructions.append(cf.ArtificialInstr("ROT_TWO", lineno=lineno))
                case 2:
                    # There are two targets, so we need to move the two remaining stack arguments
                    # above the value that we just loaded.
                    arguments_instructions.append(cf.ArtificialInstr("ROT_THREE", lineno=lineno))
                case _:
                    raise AssertionError("Unexpected number of target positions.")

        assert not target_positions, "There should be no remaining target positions."

        return (
            cf.ArtificialInstr("LOAD_CONST", method_call.self, lineno=lineno),
            cf.ArtificialInstr("LOAD_METHOD", method_call.method_name, lineno=lineno),
            *move_stack_arguments_up,
            # Here, the two potential stack arguments are moved after the LOAD_METHOD instruction.
            *swap_stack_arguments,
            # Here, the two potential stack arguments are swapped so that they are in the same order
            # as they appear in the args tuple.
            *arguments_instructions,
            # Here, all arguments are passed in the correct order.
            cf.ArtificialInstr("CALL_METHOD", len(method_call.args), lineno=lineno),
        )

    @classmethod
    def generate_teardown_instructions(
        cls,
        setup_action: InstrumentationSetupAction,  # noqa: ARG003
        lineno: int | _UNSET | None,
    ) -> tuple[cf.ArtificialInstr, ...]:
        # Remove the None from the method call return value.
        return (cf.ArtificialInstr("POP_TOP", lineno=lineno),)


def extract_comparison(instr: Instr) -> PynguinCompare:
    """Extract the comparison from an instruction.

    Args:
        instr: The instruction from which to extract the comparison.

    Returns:
        The extracted comparison.
    """
    match instr.name:
        case "COMPARE_OP":
            match instr.arg:
                case Compare.LT:
                    return PynguinCompare.LT
                case Compare.LE:
                    return PynguinCompare.LE
                case Compare.EQ:
                    return PynguinCompare.EQ
                case Compare.NE:
                    return PynguinCompare.NE
                case Compare.GT:
                    return PynguinCompare.GT
                case Compare.GE:
                    return PynguinCompare.GE
                case _:
                    raise AssertionError(f"Unknown comparison op in {instr}.")
        case "CONTAINS_OP":
            return PynguinCompare.NOT_IN if instr.arg == 1 else PynguinCompare.IN
        case "IS_OP":
            # Beginning with 3.9, there are separate OPs for various comparisons.
            # Map them back to the old operations, so we can use the enum from the
            # bytecode library.
            return PynguinCompare.IS_NOT if instr.arg == 1 else PynguinCompare.IS
        case _:
            raise AssertionError(f"Unknown comparison in {instr}.")


class BranchCoverageInstrumentation(transformer.BranchCoverageInstrumentationAdapter):
    """Specialized instrumentation adapter for branch coverage in Python 3.10."""

    _logger = logging.getLogger(__name__)

    instructions_generator: ClassVar[type[InstrumentationInstructionsGenerator]] = (
        Python310InstrumentationInstructionsGenerator
    )

    extract_comparison: ExtractComparisonFunction = staticmethod(extract_comparison)

    def __init__(self, subject_properties: tracer.SubjectProperties) -> None:  # noqa: D107
        self._subject_properties = subject_properties

    def visit_node(  # noqa: D102
        self,
        ast_info: transformer.AstInfo | None,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
    ) -> None:
        maybe_jump_index = JUMP_OP_POS
        maybe_jump = node.try_get_instruction(maybe_jump_index)

        if maybe_jump is None:
            return

        if (
            ast_info is not None
            and isinstance(maybe_jump.lineno, int)
            and not ast_info.should_cover_conditional_statement(maybe_jump.lineno)
        ):
            return

        if maybe_jump.name == "FOR_ITER":
            self.visit_for_loop(
                ast_info,
                cfg,
                code_object_id,
                node,
                maybe_jump,
                maybe_jump_index,
            )
            return

        if not maybe_jump.is_cond_jump():
            return

        try:
            maybe_compare_index, maybe_compare = node.find_instruction_by_original_index(
                COMPARE_OP_POS,
            )
        except IndexError:
            pass
        else:
            if maybe_compare.name in COMPARE_NAMES:
                self.visit_compare_based_conditional_jump(
                    ast_info,
                    cfg,
                    code_object_id,
                    node,
                    maybe_compare,
                    maybe_compare_index,
                )
                return

        if maybe_jump.name == "JUMP_IF_NOT_EXC_MATCH":
            self.visit_exception_based_conditional_jump(
                ast_info,
                cfg,
                code_object_id,
                node,
                maybe_jump,
                maybe_jump_index,
            )
            return

        self.visit_bool_based_conditional_jump(
            ast_info,
            cfg,
            code_object_id,
            node,
            maybe_jump,
            maybe_jump_index,
        )

    def visit_for_loop(  # noqa: D102, PLR0917
        self,
        ast_info: transformer.AstInfo | None,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
    ) -> None:
        lineno = instr.lineno

        predicate_id = self._subject_properties.register_predicate(
            tracer.PredicateMetaData(
                line_no=lineno,  # type: ignore[arg-type]
                code_object_id=code_object_id,
                node=node,
            )
        )

        for_loop_body = node.basic_block.next_block
        for_loop_natural_exit = instr.arg

        assert isinstance(for_loop_body, BasicBlock)
        assert isinstance(for_loop_natural_exit, BasicBlock)

        self.visit_for_loop_body(for_loop_body, predicate_id, lineno)
        self.visit_for_loop_natural_exit(for_loop_natural_exit, predicate_id, lineno)

    def visit_for_loop_body(
        self,
        for_loop_body: cf.BasicBlock,
        predicate_id: int,
        lineno: int | _UNSET | None,
    ) -> None:
        """Instrument the body of a for-loop.

        Args:
            for_loop_body: The basic block representing the body of the for-loop.
            predicate_id: The ID of the predicate to be registered.
            lineno: The line number of the first instruction in the for-loop body.
        """
        # Insert a call to the tracer before the for-loop body.
        for_loop_body[before(0)] = self.instructions_generator.generate_instructions(
            InstrumentationSetupAction.NO_ACTION,
            InstrumentationMethodCall(
                self._subject_properties.instrumentation_tracer,
                tracer.InstrumentationExecutionTracer.executed_bool_predicate.__name__,
                (
                    InstrumentationConstantLoad(value=True),
                    InstrumentationConstantLoad(value=predicate_id),
                ),
            ),
            lineno,
        )

    def visit_for_loop_natural_exit(
        self,
        for_loop_natural_exit: cf.BasicBlock,
        predicate_id: int,
        lineno: int | _UNSET | None,
    ) -> None:
        """Instrument the natural exit of a for-loop.

        Args:
            for_loop_natural_exit: The basic block representing the natural exit of the for-loop.
            predicate_id: The ID of the predicate to be registered.
            lineno: The line number of the first instruction in the for-loop without yielding.
        """
        # Insert a call to the tracer before the NOP instruction that we added in the transformer.
        for_loop_natural_exit[before(0)] = self.instructions_generator.generate_instructions(
            InstrumentationSetupAction.NO_ACTION,
            InstrumentationMethodCall(
                self._subject_properties.instrumentation_tracer,
                tracer.InstrumentationExecutionTracer.executed_bool_predicate.__name__,
                (
                    InstrumentationConstantLoad(value=False),
                    InstrumentationConstantLoad(value=predicate_id),
                ),
            ),
            lineno,
        )

    def visit_compare_based_conditional_jump(  # noqa: D102, PLR0917
        self,
        ast_info: transformer.AstInfo | None,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
    ) -> None:
        predicate_id = self._subject_properties.register_predicate(
            tracer.PredicateMetaData(
                line_no=instr.lineno,  # type: ignore[arg-type]
                code_object_id=code_object_id,
                node=node,
            )
        )

        compare = self.extract_comparison(instr)

        # Insert instructions right before the comparison.
        # We duplicate the values on top of the stack and report
        # them to the tracer.
        node.basic_block[before(instr_index)] = self.instructions_generator.generate_instructions(
            InstrumentationSetupAction.COPY_FIRST_TWO,
            InstrumentationMethodCall(
                self._subject_properties.instrumentation_tracer,
                tracer.InstrumentationExecutionTracer.executed_compare_predicate.__name__,
                (
                    InstrumentationStackValue.SECOND,
                    InstrumentationStackValue.FIRST,
                    InstrumentationConstantLoad(value=predicate_id),
                    InstrumentationConstantLoad(value=compare),
                ),
            ),
            instr.lineno,
        )

    def visit_exception_based_conditional_jump(  # noqa: D102, PLR0917
        self,
        ast_info: transformer.AstInfo | None,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
    ) -> None:
        predicate_id = self._subject_properties.register_predicate(
            tracer.PredicateMetaData(
                line_no=instr.lineno,  # type: ignore[arg-type]
                code_object_id=code_object_id,
                node=node,
            )
        )

        # Insert instructions right before the conditional jump.
        # We duplicate the values on top of the stack and report
        # them to the tracer.
        node.basic_block[before(instr_index)] = self.instructions_generator.generate_instructions(
            InstrumentationSetupAction.COPY_FIRST_TWO,
            InstrumentationMethodCall(
                self._subject_properties.instrumentation_tracer,
                tracer.InstrumentationExecutionTracer.executed_exception_match.__name__,
                (
                    InstrumentationStackValue.SECOND,
                    InstrumentationStackValue.FIRST,
                    InstrumentationConstantLoad(value=predicate_id),
                ),
            ),
            instr.lineno,
        )

    def visit_bool_based_conditional_jump(  # noqa: D102, PLR0917
        self,
        ast_info: transformer.AstInfo | None,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
    ) -> None:
        predicate_id = self._subject_properties.register_predicate(
            tracer.PredicateMetaData(
                line_no=instr.lineno,  # type: ignore[arg-type]
                code_object_id=code_object_id,
                node=node,
            )
        )

        # Insert instructions right before the conditional jump.
        # We duplicate the value on top of the stack and report
        # it to the tracer.
        node.basic_block[before(instr_index)] = self.instructions_generator.generate_instructions(
            InstrumentationSetupAction.COPY_FIRST,
            InstrumentationMethodCall(
                self._subject_properties.instrumentation_tracer,
                tracer.InstrumentationExecutionTracer.executed_bool_predicate.__name__,
                (
                    InstrumentationStackValue.FIRST,
                    InstrumentationConstantLoad(value=predicate_id),
                ),
            ),
            instr.lineno,
        )

    def visit_cfg(  # noqa: D102
        self,
        ast_info: transformer.AstInfo | None,
        cfg: cf.CFG,
        code_object_id: int,
    ) -> None:
        node = cfg.first_basic_block_node

        assert node is not None, "The CFG must have at least one basic block node."

        # Use line number of first instruction
        lineno = node.basic_block[0].lineno  # type: ignore[union-attr]

        # Insert instructions at the beginning.
        node.basic_block[before(0)] = self.instructions_generator.generate_instructions(
            InstrumentationSetupAction.NO_ACTION,
            InstrumentationMethodCall(
                self._subject_properties.instrumentation_tracer,
                tracer.InstrumentationExecutionTracer.executed_code_object.__name__,
                (InstrumentationConstantLoad(value=code_object_id),),
            ),
            lineno,
        )


class LineCoverageInstrumentation(transformer.LineCoverageInstrumentationAdapter):
    """Specialized instrumentation adapter for line coverage in Python 3.10."""

    _logger = logging.getLogger(__name__)

    instructions_generator: ClassVar[type[InstrumentationInstructionsGenerator]] = (
        Python310InstrumentationInstructionsGenerator
    )

    def __init__(  # noqa: D107
        self,
        subject_properties: tracer.SubjectProperties,
    ) -> None:
        self._subject_properties = subject_properties

    def should_instrument_line(self, instr: Instr, lineno: int | _UNSET | None) -> bool:
        """Check if the line should be instrumented.

        Args:
            instr: The instruction to check.
            lineno: The line number to check against.

        Returns:
            True if the line should be instrumented, False otherwise.
        """
        return instr.lineno != lineno

    def visit_node(  # noqa: D102
        self,
        ast_info: transformer.AstInfo | None,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
    ) -> None:
        if cfg.bytecode_cfg.filename == AST_FILENAME:
            # Do not instrument the AST files.
            return

        lineno: int | _UNSET | None = None

        for instr_index, instr in node.instrumentation_original_instructions:
            if (
                ast_info is not None
                and isinstance(instr.lineno, int)
                and not ast_info.should_cover_line(instr.lineno)
            ):
                continue

            if self.should_instrument_line(instr, lineno):
                lineno = instr.lineno

                self.visit_line(ast_info, cfg, code_object_id, node, instr, instr_index)

    def visit_line(  # noqa: D102, PLR0917
        self,
        ast_info: transformer.AstInfo | None,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
    ) -> None:
        line_id = self._subject_properties.register_line(
            tracer.LineMetaData(
                code_object_id=code_object_id,
                file_name=cfg.bytecode_cfg.filename,
                line_number=instr.lineno,  # type: ignore[arg-type]
            )
        )

        # Insert instructions before each line instructions.
        node.basic_block[before(instr_index)] = self.instructions_generator.generate_instructions(
            InstrumentationSetupAction.NO_ACTION,
            InstrumentationMethodCall(
                self._subject_properties.instrumentation_tracer,
                tracer.InstrumentationExecutionTracer.track_line_visit.__name__,
                (InstrumentationConstantLoad(value=line_id),),
            ),
            instr.lineno,
        )


class CheckedCoverageInstrumentation(transformer.CheckedCoverageInstrumentationAdapter):
    """Specialized instrumentation adapter for checked coverage in Python 3.10."""

    _logger = logging.getLogger(__name__)

    instructions_generator: ClassVar[type[InstrumentationInstructionsGenerator]] = (
        Python310InstrumentationInstructionsGenerator
    )

    def __init__(self, subject_properties: tracer.SubjectProperties) -> None:  # noqa: D107
        self._subject_properties = subject_properties

    def should_instrument_line(self, instr: Instr, lineno: int | _UNSET | None) -> bool:
        """Check if the line should be instrumented.

        Args:
            instr: The instruction to check.
            lineno: The line number to check against.

        Returns:
            True if the line should be instrumented, False otherwise.
        """
        return instr.lineno != lineno

    def visit_node(  # noqa: D102
        self,
        ast_info: transformer.AstInfo | None,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
    ) -> None:
        lineno: int | _UNSET | None = None

        for instr_original_index, (instr_index, instr) in enumerate(
            node.instrumentation_original_instructions
        ):
            if (
                ast_info is not None
                and isinstance(instr.lineno, int)
                and not ast_info.should_cover_line(instr.lineno)
            ):
                continue

            # Register all lines available
            if cfg.bytecode_cfg.filename != AST_FILENAME and self.should_instrument_line(
                instr, lineno
            ):
                lineno = instr.lineno
                self.visit_line(
                    ast_info,
                    cfg,
                    code_object_id,
                    node,
                    instr,
                    instr_index,
                    instr_original_index,
                )

            # Perform the actual instrumentation
            for operations, method in self.METHODS.items():
                if instr.name in operations:
                    method(
                        self,
                        ast_info,
                        cfg,
                        code_object_id,
                        node,
                        instr,
                        instr_index,
                        instr_original_index,
                    )
                    break

    def visit_line(  # noqa: D102, PLR0917
        self,
        ast_info: transformer.AstInfo | None,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
        instr_original_index: int,
    ) -> None:
        self._subject_properties.register_line(
            tracer.LineMetaData(
                code_object_id=code_object_id,
                file_name=cfg.bytecode_cfg.filename,
                line_number=instr.lineno,  # type: ignore[arg-type]
            )
        )

    def visit_generic(  # noqa: D102, PLR0917
        self,
        ast_info: transformer.AstInfo | None,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
        instr_original_index: int,
    ) -> None:
        # Instrumentation before the original instruction
        node.basic_block[before(instr_index)] = self.instructions_generator.generate_instructions(
            InstrumentationSetupAction.NO_ACTION,
            InstrumentationMethodCall(
                self._subject_properties.instrumentation_tracer,
                tracer.InstrumentationExecutionTracer.track_generic.__name__,
                (
                    InstrumentationConstantLoad(value=cfg.bytecode_cfg.filename),
                    InstrumentationConstantLoad(value=code_object_id),
                    InstrumentationConstantLoad(value=node.index),
                    InstrumentationConstantLoad(value=instr.opcode),
                    InstrumentationConstantLoad(value=instr.lineno),
                    InstrumentationConstantLoad(value=instr_original_index),
                ),
            ),
            instr.lineno,
        )

    def visit_local_access(  # noqa: D102, PLR0917
        self,
        ast_info: transformer.AstInfo | None,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
        instr_original_index: int,
    ) -> None:
        instructions = self.instructions_generator.generate_instructions(
            InstrumentationSetupAction.NO_ACTION,
            InstrumentationMethodCall(
                self._subject_properties.instrumentation_tracer,
                tracer.InstrumentationExecutionTracer.track_memory_access.__name__,
                (
                    InstrumentationConstantLoad(value=cfg.bytecode_cfg.filename),
                    InstrumentationConstantLoad(value=code_object_id),
                    InstrumentationConstantLoad(value=node.index),
                    InstrumentationConstantLoad(value=instr.opcode),
                    InstrumentationConstantLoad(value=instr.lineno),
                    InstrumentationConstantLoad(value=instr_original_index),
                    InstrumentationConstantLoad(value=instr.arg),  # type: ignore[arg-type]
                    InstrumentationFastLoad(name=instr.arg),  # type: ignore[arg-type]
                ),
            ),
            instr.lineno,
        )

        match instr.name:
            case "DELETE_FAST":
                # Instrumentation before the original instruction
                # (otherwise we can not read the data)
                node.basic_block[before(instr_index)] = instructions
            case "LOAD_FAST" | "STORE_FAST":
                # Instrumentation after the original instruction
                node.basic_block[after(instr_index)] = instructions

    def visit_attr_access(  # noqa: D102, PLR0917
        self,
        ast_info: transformer.AstInfo | None,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
        instr_original_index: int,
    ) -> None:
        method_call = InstrumentationMethodCall(
            self._subject_properties.instrumentation_tracer,
            tracer.InstrumentationExecutionTracer.track_attribute_access.__name__,
            (
                InstrumentationConstantLoad(value=cfg.bytecode_cfg.filename),
                InstrumentationConstantLoad(value=code_object_id),
                InstrumentationConstantLoad(value=node.index),
                InstrumentationConstantLoad(value=instr.opcode),
                InstrumentationConstantLoad(value=instr.lineno),
                InstrumentationConstantLoad(value=instr_original_index),
                InstrumentationConstantLoad(value=instr.arg),  # type: ignore[arg-type]
                InstrumentationStackValue.FIRST,
            ),
        )

        match instr.name:
            case "LOAD_ATTR" | "DELETE_ATTR" | "IMPORT_FROM" | "LOAD_METHOD":
                # Instrumentation before the original instruction
                node.basic_block[before(instr_index)] = (
                    self.instructions_generator.generate_instructions(
                        InstrumentationSetupAction.COPY_FIRST,
                        method_call,
                        instr.lineno,
                    )
                )
            case "STORE_ATTR":
                # Instrumentation mostly after the original instruction
                node.basic_block[override(instr_index)] = (
                    self.instructions_generator.generate_overriding_instructions(
                        InstrumentationSetupAction.COPY_FIRST_SHIFT_DOWN_TWO,
                        instr,
                        method_call,
                        instr.lineno,
                    )
                )

    def visit_subscr_access(  # noqa: D102, PLR0917
        self,
        ast_info: transformer.AstInfo | None,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
        instr_original_index: int,
    ) -> None:
        method_call = InstrumentationMethodCall(
            self._subject_properties.instrumentation_tracer,
            tracer.InstrumentationExecutionTracer.track_attribute_access.__name__,
            (
                InstrumentationConstantLoad(value=cfg.bytecode_cfg.filename),
                InstrumentationConstantLoad(value=code_object_id),
                InstrumentationConstantLoad(value=node.index),
                InstrumentationConstantLoad(value=instr.opcode),
                InstrumentationConstantLoad(value=instr.lineno),
                InstrumentationConstantLoad(value=instr_original_index),
                InstrumentationConstantLoad(value=None),
                InstrumentationStackValue.FIRST,
            ),
        )

        match instr.name:
            case "STORE_SUBSCR":
                # Instrumentation mostly after the original instruction
                node.basic_block[override(instr_index)] = (
                    self.instructions_generator.generate_overriding_instructions(
                        InstrumentationSetupAction.COPY_SECOND_SHIFT_DOWN_THREE,
                        instr,
                        method_call,
                        instr.lineno,
                    )
                )
            case "DELETE_SUBSCR":
                # Instrumentation mostly after the original instruction
                node.basic_block[override(instr_index)] = (
                    self.instructions_generator.generate_overriding_instructions(
                        InstrumentationSetupAction.COPY_SECOND_SHIFT_DOWN_TWO,
                        instr,
                        method_call,
                        instr.lineno,
                    )
                )
            case "BINARY_SUBSCR":
                # Instrumentation before the original instruction
                node.basic_block[before(instr_index)] = (
                    self.instructions_generator.generate_instructions(
                        InstrumentationSetupAction.COPY_SECOND,
                        method_call,
                        instr.lineno,
                    )
                )

    def visit_name_access(  # noqa: D102, PLR0917
        self,
        ast_info: transformer.AstInfo | None,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
        instr_original_index: int,
    ) -> None:
        instructions = self.instructions_generator.generate_instructions(
            InstrumentationSetupAction.NO_ACTION,
            InstrumentationMethodCall(
                self._subject_properties.instrumentation_tracer,
                tracer.InstrumentationExecutionTracer.track_memory_access.__name__,
                (
                    InstrumentationConstantLoad(value=cfg.bytecode_cfg.filename),
                    InstrumentationConstantLoad(value=code_object_id),
                    InstrumentationConstantLoad(value=node.index),
                    InstrumentationConstantLoad(value=instr.opcode),
                    InstrumentationConstantLoad(value=instr.lineno),
                    InstrumentationConstantLoad(value=instr_original_index),
                    InstrumentationConstantLoad(value=instr.arg),  # type: ignore[arg-type]
                    InstrumentationNameLoad(name=instr.arg),  # type: ignore[arg-type]
                ),
            ),
            instr.lineno,
        )

        match instr.name:
            case "DELETE_NAME":
                # Instrumentation before the original instruction
                # (otherwise we can not read the data)
                node.basic_block[before(instr_index)] = instructions
            case "STORE_NAME" | "LOAD_NAME" | "IMPORT_NAME":
                # Instrumentation after the original instruction
                node.basic_block[after(instr_index)] = instructions

    def visit_import_name_access(  # noqa: D102, PLR0917
        self,
        ast_info: transformer.AstInfo | None,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
        instr_original_index: int,
    ) -> None:
        node.basic_block[after(instr_index)] = self.instructions_generator.generate_instructions(
            InstrumentationSetupAction.COPY_FIRST,
            InstrumentationMethodCall(
                self._subject_properties.instrumentation_tracer,
                tracer.InstrumentationExecutionTracer.track_memory_access.__name__,
                (
                    InstrumentationConstantLoad(value=cfg.bytecode_cfg.filename),
                    InstrumentationConstantLoad(value=code_object_id),
                    InstrumentationConstantLoad(value=node.index),
                    InstrumentationConstantLoad(value=instr.opcode),
                    InstrumentationConstantLoad(value=instr.lineno),
                    InstrumentationConstantLoad(value=instr_original_index),
                    InstrumentationConstantLoad(value=instr.arg),  # type: ignore[arg-type]
                    InstrumentationStackValue.FIRST,
                ),
            ),
            instr.lineno,
        )

    def visit_global_access(  # noqa: D102, PLR0917
        self,
        ast_info: transformer.AstInfo | None,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
        instr_original_index: int,
    ) -> None:
        name = extract_name(instr.arg)
        assert name is not None, "Global access must have a name."

        instructions = self.instructions_generator.generate_instructions(
            InstrumentationSetupAction.NO_ACTION,
            InstrumentationMethodCall(
                self._subject_properties.instrumentation_tracer,
                tracer.InstrumentationExecutionTracer.track_memory_access.__name__,
                (
                    InstrumentationConstantLoad(value=cfg.bytecode_cfg.filename),
                    InstrumentationConstantLoad(value=code_object_id),
                    InstrumentationConstantLoad(value=node.index),
                    InstrumentationConstantLoad(value=instr.opcode),
                    InstrumentationConstantLoad(value=instr.lineno),
                    InstrumentationConstantLoad(value=instr_original_index),
                    InstrumentationConstantLoad(value=name),
                    InstrumentationGlobalLoad(name=name),
                ),
            ),
            instr.lineno,
        )

        match instr.name:
            case "DELETE_GLOBAL":
                # Instrumentation before the original instruction
                # (otherwise we can not read the data)
                node.basic_block[before(instr_index)] = instructions
            case "STORE_GLOBAL" | "LOAD_GLOBAL":
                # Instrumentation after the original instruction
                node.basic_block[after(instr_index)] = instructions

    def visit_deref_access(  # noqa: D102, PLR0917
        self,
        ast_info: transformer.AstInfo | None,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
        instr_original_index: int,
    ) -> None:
        value_instruction = (
            InstrumentationClassDeref(name=instr.arg)  # type: ignore[arg-type]
            if instr.name == "LOAD_CLASSDEREF"
            else InstrumentationDeref(name=instr.arg)  # type: ignore[arg-type]
        )

        instructions = self.instructions_generator.generate_instructions(
            InstrumentationSetupAction.NO_ACTION,
            InstrumentationMethodCall(
                self._subject_properties.instrumentation_tracer,
                tracer.InstrumentationExecutionTracer.track_memory_access.__name__,
                (
                    InstrumentationConstantLoad(value=cfg.bytecode_cfg.filename),
                    InstrumentationConstantLoad(value=code_object_id),
                    InstrumentationConstantLoad(value=node.index),
                    InstrumentationConstantLoad(value=instr.opcode),
                    InstrumentationConstantLoad(value=instr.lineno),
                    InstrumentationConstantLoad(value=instr_original_index),
                    InstrumentationConstantLoad(value=instr.arg),  # type: ignore[arg-type]
                    value_instruction,
                ),
            ),
            instr.lineno,
        )

        match instr.name:
            case "DELETE_DEREF":
                # Instrumentation before the original instruction
                # (otherwise we can not read the data)
                node.basic_block[before(instr_index)] = instructions
            case "STORE_DEREF" | "LOAD_DEREF" | "LOAD_CLASSDEREF":
                # Instrumentation after the original instruction
                node.basic_block[after(instr_index)] = instructions

    def visit_jump(  # noqa: D102, PLR0917
        self,
        ast_info: transformer.AstInfo | None,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
        instr_original_index: int,
    ) -> None:
        # Instrumentation before the original instruction
        node.basic_block[before(instr_index)] = self.instructions_generator.generate_instructions(
            InstrumentationSetupAction.NO_ACTION,
            InstrumentationMethodCall(
                self._subject_properties.instrumentation_tracer,
                tracer.InstrumentationExecutionTracer.track_jump.__name__,
                (
                    InstrumentationConstantLoad(value=cfg.bytecode_cfg.filename),
                    InstrumentationConstantLoad(value=code_object_id),
                    InstrumentationConstantLoad(value=node.index),
                    InstrumentationConstantLoad(value=instr.opcode),
                    InstrumentationConstantLoad(value=instr.lineno),
                    InstrumentationConstantLoad(value=instr_original_index),
                    InstrumentationConstantLoad(value=cfg.bytecode_cfg.get_block_index(instr.arg)),  # type: ignore[arg-type]
                ),
            ),
            instr.lineno,
        )

    def visit_call(  # noqa: D102, PLR0917
        self,
        ast_info: transformer.AstInfo | None,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
        instr_original_index: int,
    ) -> None:
        # Trace argument only for calls with integer arguments
        argument = instr.arg if isinstance(instr.arg, int) and instr.arg != UNSET else None

        # Instrumentation before the original instruction
        node.basic_block[before(instr_index)] = self.instructions_generator.generate_instructions(
            InstrumentationSetupAction.NO_ACTION,
            InstrumentationMethodCall(
                self._subject_properties.instrumentation_tracer,
                tracer.InstrumentationExecutionTracer.track_call.__name__,
                (
                    InstrumentationConstantLoad(value=cfg.bytecode_cfg.filename),
                    InstrumentationConstantLoad(value=code_object_id),
                    InstrumentationConstantLoad(value=node.index),
                    InstrumentationConstantLoad(value=instr.opcode),
                    InstrumentationConstantLoad(value=instr.lineno),
                    InstrumentationConstantLoad(value=instr_original_index),
                    InstrumentationConstantLoad(value=argument),
                ),
            ),
            instr.lineno,
        )

    def visit_return(  # noqa: D102, PLR0917
        self,
        ast_info: transformer.AstInfo | None,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
        instr_original_index: int,
    ) -> None:
        # Instrumentation before the original instruction
        # (otherwise we can not read the data)
        node.basic_block[before(instr_index)] = self.instructions_generator.generate_instructions(
            InstrumentationSetupAction.NO_ACTION,
            InstrumentationMethodCall(
                self._subject_properties.instrumentation_tracer,
                tracer.InstrumentationExecutionTracer.track_return.__name__,
                (
                    InstrumentationConstantLoad(value=cfg.bytecode_cfg.filename),
                    InstrumentationConstantLoad(value=code_object_id),
                    InstrumentationConstantLoad(value=node.index),
                    InstrumentationConstantLoad(value=instr.opcode),
                    InstrumentationConstantLoad(value=instr.lineno),
                    InstrumentationConstantLoad(value=instr_original_index),
                ),
            ),
            instr.lineno,
        )

    METHODS: ClassVar[
        dict[
            tuple[str, ...],
            CheckedCoverageInstrumentationVisitorMethod,
        ]
    ] = {
        OPERATION_NAMES: visit_generic,
        ACCESS_FAST_NAMES: visit_local_access,
        ATTRIBUTES_NAMES: visit_attr_access,
        ACCESS_SUBSCR_NAMES: visit_subscr_access,
        ACCESS_NAME_NAMES: visit_name_access,
        IMPORT_NAME_NAMES: visit_import_name_access,
        ACCESS_GLOBAL_NAMES: visit_global_access,
        ACCESS_DEREF_NAMES: visit_deref_access,
        JUMP_NAMES: visit_jump,
        CALL_NAMES: visit_call,
        RETURNING_NAMES: visit_return,
    }


class DynamicSeedingInstrumentation(transformer.DynamicSeedingInstrumentationAdapter):
    """Specialized instrumentation adapter for dynamic constant seeding in Python 3.10."""

    _logger = logging.getLogger(__name__)

    instructions_generator: ClassVar[type[InstrumentationInstructionsGenerator]] = (
        Python310InstrumentationInstructionsGenerator
    )

    # If one of the considered string functions needing no argument is used in the if
    # statement, it will be loaded in the third last position. After it comes the
    # call of the method and the jump operation.
    STRING_FUNC_POS: ClassVar[int] = -3

    # If one of the considered string functions needing one argument is used in the if
    # statement, it will be loaded in the fourth last position. After it comes the
    # load of the argument, the call of the method and the jump operation.
    STRING_FUNC_POS_WITH_ARG: ClassVar[int] = -4

    def __init__(  # noqa: D107
        self, dynamic_constant_provider: DynamicConstantProvider
    ):
        self._dynamic_constant_provider = dynamic_constant_provider

    def extract_method_name(self, instr: Instr) -> str | None:
        """Extract the method name from the instruction.

        Args:
            instr: The instruction to extract the method name from.

        Returns:
            The method name if it is a call method instruction, None otherwise.
        """
        return extract_name(instr.arg) if instr.name == "LOAD_METHOD" else None

    def visit_node(  # noqa: D102
        self,
        ast_info: transformer.AstInfo | None,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
    ) -> None:
        if (
            ast_info is not None
            and (jump_instr := node.try_get_instruction(JUMP_OP_POS)) is not None
            and isinstance(jump_instr.lineno, int)
            and not ast_info.should_cover_line(jump_instr.lineno)
        ):
            return

        maybe_compare_index = COMPARE_OP_POS
        maybe_compare = node.try_get_instruction(maybe_compare_index)

        if (
            maybe_compare is not None
            and isinstance(maybe_compare, Instr)
            and maybe_compare.name == "COMPARE_OP"
        ):
            self.visit_compare_op(
                ast_info,
                cfg,
                code_object_id,
                node,
                maybe_compare,
                maybe_compare_index,
            )
            return

        maybe_string_func_index = self.STRING_FUNC_POS
        maybe_string_func = node.try_get_instruction(maybe_string_func_index)

        if (
            isinstance(maybe_string_func, Instr)
            and (method_name := self.extract_method_name(maybe_string_func)) is not None
            and method_name in DynamicConstantProvider.STRING_FUNCTION_LOOKUP
        ):
            self.visit_string_function_without_arg(
                ast_info,
                cfg,
                code_object_id,
                node,
                maybe_string_func,
                maybe_string_func_index,
            )
            return

        maybe_string_func_with_arg_index = self.STRING_FUNC_POS_WITH_ARG
        maybe_string_func_with_arg = node.try_get_instruction(maybe_string_func_with_arg_index)

        if (
            isinstance(maybe_string_func_with_arg, Instr)
            and (method_name := self.extract_method_name(maybe_string_func_with_arg)) is not None
        ):
            match method_name:
                case "startswith":
                    self.visit_startswith_function(
                        ast_info,
                        cfg,
                        code_object_id,
                        node,
                        maybe_string_func_with_arg,
                        maybe_string_func_with_arg_index,
                    )
                case "endswith":
                    self.visit_endswith_function(
                        ast_info,
                        cfg,
                        code_object_id,
                        node,
                        maybe_string_func_with_arg,
                        maybe_string_func_with_arg_index,
                    )

    def visit_compare_op(  # noqa: D102, PLR0917
        self,
        ast_info: transformer.AstInfo | None,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
    ) -> None:
        node.basic_block[before(instr_index)] = (
            *self.instructions_generator.generate_instructions(
                InstrumentationSetupAction.COPY_FIRST,
                InstrumentationMethodCall(
                    self._dynamic_constant_provider,
                    DynamicConstantProvider.add_value.__name__,
                    (InstrumentationStackValue.FIRST,),
                ),
                instr.lineno,
            ),
            *self.instructions_generator.generate_instructions(
                InstrumentationSetupAction.COPY_SECOND,
                InstrumentationMethodCall(
                    self._dynamic_constant_provider,
                    DynamicConstantProvider.add_value.__name__,
                    (InstrumentationStackValue.FIRST,),
                ),
                instr.lineno,
            ),
        )

        self._logger.debug("Instrumented compare_op")

    def visit_string_function_without_arg(  # noqa: D102, PLR0917
        self,
        ast_info: transformer.AstInfo | None,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
    ) -> None:
        node.basic_block[before(instr_index + 1)] = (
            self.instructions_generator.generate_instructions(
                InstrumentationSetupAction.COPY_FIRST,
                InstrumentationMethodCall(
                    self._dynamic_constant_provider,
                    DynamicConstantProvider.add_value_for_strings.__name__,
                    (
                        InstrumentationStackValue.FIRST,
                        InstrumentationConstantLoad(value=self.extract_method_name(instr)),
                    ),
                ),
                instr.lineno,
            )
        )

        self._logger.info("Instrumented string function")

    def visit_startswith_function(  # noqa: D102, PLR0917
        self,
        ast_info: transformer.AstInfo | None,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
    ) -> None:
        node.basic_block[before(instr_index + 2)] = (
            self.instructions_generator.generate_instructions(
                InstrumentationSetupAction.ADD_FIRST_TWO_REVERSED,
                InstrumentationMethodCall(
                    self._dynamic_constant_provider,
                    DynamicConstantProvider.add_value.__name__,
                    (InstrumentationStackValue.FIRST,),
                ),
                instr.lineno,
            )
        )

        self._logger.info("Instrumented startswith function")

    def visit_endswith_function(  # noqa: D102, PLR0917
        self,
        ast_info: transformer.AstInfo | None,
        cfg: cf.CFG,
        code_object_id: int,
        node: cf.BasicBlockNode,
        instr: Instr,
        instr_index: int,
    ) -> None:
        node.basic_block[before(instr_index + 2)] = (
            self.instructions_generator.generate_instructions(
                InstrumentationSetupAction.ADD_FIRST_TWO,
                InstrumentationMethodCall(
                    self._dynamic_constant_provider,
                    DynamicConstantProvider.add_value.__name__,
                    (InstrumentationStackValue.FIRST,),
                ),
                instr.lineno,
            )
        )

        self._logger.info("Instrumented endswith function")
