#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
# Idea taken from the pyChecco project, see:
# https://github.com/ipsw1/pychecco

# mypy does not detect, that some enums are only accessed if a specific version is used
# mypy: ignore-errors

"""Provides offset calculations for stack effects based on the used python version."""
import sys
from typing import Dict, Tuple

import pynguin.utils.opcodes as op


def _get_base_se() -> Dict[int, Tuple[int, int]]:
    """Initialize all unconditional opcode stack effects
    that are shared between all used python versions of pynguin."""
    return {
        # OP NAME: (POP, PUSH)
        op.POP_TOP: (1, 0),
        op.ROT_TWO: (2, 2),
        op.ROT_THREE: (3, 3),
        op.ROT_FOUR: (4, 4),
        op.DUP_TOP: (0, 1),
        op.DUP_TOP_TWO: (0, 2),
        op.NOP: (0, 0),
        op.UNARY_POSITIVE: (1, 1),
        op.UNARY_NEGATIVE: (1, 1),
        op.UNARY_NOT: (1, 1),
        op.UNARY_INVERT: (1, 1),
        op.BINARY_MATRIX_MULTIPLY: (2, 1),
        op.INPLACE_MATRIX_MULTIPLY: (2, 1),
        op.BINARY_POWER: (2, 1),
        op.BINARY_MULTIPLY: (2, 1),
        op.BINARY_MODULO: (2, 1),
        op.BINARY_ADD: (2, 1),
        op.BINARY_SUBTRACT: (2, 1),
        op.BINARY_SUBSCR: (2, 1),
        op.BINARY_FLOOR_DIVIDE: (2, 1),
        op.BINARY_TRUE_DIVIDE: (2, 1),
        op.INPLACE_FLOOR_DIVIDE: (2, 1),
        op.INPLACE_TRUE_DIVIDE: (2, 1),
        op.BEFORE_ASYNC_WITH: (0, 1),
        op.END_ASYNC_FOR: (7, 0),  # TODO conditional 0 pops?
        op.INPLACE_ADD: (2, 1),
        op.INPLACE_SUBTRACT: (2, 1),
        op.INPLACE_MULTIPLY: (2, 1),
        op.INPLACE_MODULO: (2, 1),
        op.STORE_SUBSCR: (3, 0),
        op.DELETE_SUBSCR: (2, 0),
        op.BINARY_LSHIFT: (2, 1),
        op.BINARY_RSHIFT: (2, 1),
        op.BINARY_AND: (2, 1),
        op.BINARY_XOR: (2, 1),
        op.BINARY_OR: (2, 1),
        op.INPLACE_POWER: (2, 1),
        op.GET_AITER: (1, 1),
        op.GET_ANEXT: (0, 1),
        op.GET_ITER: (1, 1),
        op.GET_YIELD_FROM_ITER: (1, 1),
        op.PRINT_EXPR: (1, 0),
        op.LOAD_BUILD_CLASS: (0, 1),
        op.YIELD_FROM: (1, 0),
        op.GET_AWAITABLE: (0, 0),
        op.INPLACE_LSHIFT: (2, 1),
        op.INPLACE_RSHIFT: (2, 1),
        op.INPLACE_AND: (2, 1),
        op.INPLACE_XOR: (2, 1),
        op.INPLACE_OR: (2, 1),
        op.RETURN_VALUE: (1, 0),
        op.IMPORT_STAR: (1, 0),
        op.SETUP_ANNOTATIONS: (0, 0),
        op.YIELD_VALUE: (1, 1),
        op.POP_BLOCK: (0, 0),
        op.POP_EXCEPT: (3, 0),
        # opcodes above 90 can have an argument
        op.STORE_NAME: (1, 0),
        op.DELETE_NAME: (0, 0),
        op.STORE_ATTR: (2, 0),
        op.DELETE_ATTR: (1, 0),
        op.STORE_GLOBAL: (1, 0),
        op.DELETE_GLOBAL: (0, 0),
        op.LOAD_CONST: (0, 1),
        op.LOAD_NAME: (0, 1),
        op.LOAD_ATTR: (1, 1),
        op.COMPARE_OP: (2, 1),
        op.IMPORT_NAME: (2, 1),
        op.IMPORT_FROM: (0, 1),
        op.JUMP_FORWARD: (0, 0),
        op.JUMP_ABSOLUTE: (0, 0),
        op.POP_JUMP_IF_FALSE: (2, 1),
        op.POP_JUMP_IF_TRUE: (2, 1),
        op.LOAD_GLOBAL: (0, 1),
        op.LOAD_FAST: (0, 1),
        op.STORE_FAST: (1, 0),
        op.DELETE_FAST: (0, 0),
        op.LOAD_CLOSURE: (0, 1),
        op.LOAD_DEREF: (0, 1),
        op.STORE_DEREF: (1, 0),
        op.DELETE_DEREF: (0, 0),
        op.LIST_APPEND: (2, 1),
        op.SET_ADD: (1, 0),
        op.MAP_ADD: (3, 1),
        op.LOAD_CLASSDEREF: (0, 1),
        op.EXTENDED_ARG: (0, 0),
        op.FORMAT_VALUE: (1, 1),
        op.LOAD_METHOD: (0, 1),
    }


def _update_se_to_38(_se_lookup) -> None:
    """Add all 3.8 specific opcodes (opcodes removed later than 3.8).
    These have to be added only after the version check, otherwise the op code
    attributes will be already be deleted, causing an Attribute error.
    """
    assert (
        sys.version_info[0] == 3 and sys.version_info[1] == 8
    ), "Only call this method with python 3.8"
    _se_lookup[op.BEGIN_FINALLY] = (0, 6)

    _se_lookup[op.WITH_CLEANUP_START] = (0, 2)
    _se_lookup[op.WITH_CLEANUP_FINISH] = (3, 0)

    _se_lookup[op.END_FINALLY] = (6, 0)

    _se_lookup[op.CALL_FINALLY] = (0, 1)
    _se_lookup[op.POP_FINALLY] = (6, 0)


def _update_se_to_39(_se_lookup) -> None:
    assert (
        sys.version_info[0] == 3 and sys.version_info[1] == 9
    ), "Only call this method with python 3.9"
    # added instruction from 3.8 to 3.9
    _se_lookup[op.RERAISE] = (3, 0)
    _se_lookup[op.WITH_EXCEPT_START] = (0, 1)
    _se_lookup[op.LOAD_ASSERTION_ERROR] = (0, 1)

    _se_lookup[op.IS_OP] = (2, 1)
    _se_lookup[op.CONTAINS_OP] = (2, 1)
    _se_lookup[op.JUMP_IF_NOT_EXEC_MATCH] = (2, 0)

    # the instructions removed between 3.8 to 3.9 are not even added to the _se
    # unless the code runs with python 3.8, so need to remove something here


def _update_se_to_310(_se_lookup) -> None:
    assert (
        sys.version_info[0] == 3 and sys.version_info[1] == 10
    ), "Only call this method with python 3.10"
    _se_lookup[op.GET_LEN] = (0, 1)
    _se_lookup[op.MATCH_MAPPING] = (0, 1)
    _se_lookup[op.MATCH_SEQUENCE] = (0, 1)
    _se_lookup[op.MATCH_KEYS] = (0, 2)
    _se_lookup[op.COPY_DICT_WITHOUT_KEYS] = (2, 2)
    _se_lookup[op.ROT_N] = (0, 0)
    _se_lookup[op.RERAISE] = (3, 0)
    _se_lookup[op.GEN_START] = (1, 0)
    _se_lookup[op.MATCH_CLASS] = (2, 1)


# pylint: disable=too-many-branches, too-many-return-statements
def _conditional_se(opcode: int, arg, jump: bool) -> Tuple[int, int]:  # noqa: C901
    # jump based operations
    if opcode == op.SETUP_WITH:
        if not jump:
            return 0, 1
        return 0, 6
    if opcode == op.FOR_ITER:
        if not jump:
            return 1, 2
        return 1, 0
    if opcode in (op.JUMP_IF_TRUE_OR_POP, op.JUMP_IF_FALSE_OR_POP):
        if not jump:
            return 1, 0
        return 0, 0
    if opcode == op.SETUP_FINALLY:
        if not jump:
            return 0, 0
        return 0, 6
    # argument dependant operations
    if opcode == op.UNPACK_SEQUENCE:
        return 1, arg
    if opcode == op.UNPACK_EX:
        return 1, (arg & 0xFF) + (arg >> 8) + 1
    if opcode in (op.BUILD_TUPLE, op.BUILD_LIST, op.BUILD_SET, op.BUILD_STRING):
        return arg, 1
    if opcode == op.BUILD_MAP:
        return (2 * arg), 1
    if opcode == op.BUILD_CONST_KEY_MAP:
        return (1 + arg), 1
    if opcode == op.RAISE_VARARGS:
        return arg, 0
    if opcode == op.CALL_FUNCTION:
        return (1 + arg), 1
    if opcode == op.CALL_METHOD:
        return (2 + arg), 1
    if opcode == op.CALL_FUNCTION_KW:
        return (2 + arg), 1
    if opcode == op.CALL_FUNCTION_EX:
        # argument contains flags
        pops = 2
        if arg & 0x01 != 0:
            pops += 1
        return pops, 1
    if opcode == op.MAKE_FUNCTION:
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
        return pops, 1
    if opcode == op.BUILD_SLICE:
        if arg == 3:
            return 3, 1
        return 2, 1
    raise ValueError(f"The opcode {opcode} isn't recognized.")


# pylint:disable=too-few-public-methods.
class StackEffect:
    """Utility class for all stack effect calculations."""

    assert sys.version_info >= (3, 8), "Unsupported python version"
    assert sys.version_info <= (3, 10), "Unsupported python version"

    _se_lookup: Dict[int, Tuple[int, int]] = _get_base_se()
    if sys.version_info[1] == 8:
        _update_se_to_38(_se_lookup)
    if sys.version_info[1] == 9:
        _update_se_to_39(_se_lookup)
    if sys.version_info[1] == 10:
        _update_se_to_310(_se_lookup)

    @staticmethod
    def stack_effect(opcode: int, arg, jump: bool = False) -> Tuple[int, int]:
        """Get the stack effect as a tuple of number of pops and number of pushes
        for an opcode.

        Args:
            opcode: The opcode, to get the pops and pushes for.
            arg: numeric argument to operation (if any), otherwise None
            jump: if the code has a jump and jump is true

        Returns:
            A tuple containing the number of pops and pushes as integer.
        """
        assert (
            opcode != op.SETUP_ASYNC_WITH
        ), "Uncertain stack effect for SETUP_ASYNC_WITH"

        if opcode in StackEffect._se_lookup:
            return StackEffect._se_lookup[opcode]

        if sys.version_info[1] == 8:
            # check 3.8 specific conditional opcodes
            if opcode == op.CALL_FINALLY:
                if not jump:
                    return 0, 1
                return 0, 0

        if sys.version_info[1] == 9:
            pass  # no 3.9 specific conditional opcodes

        if sys.version_info[1] == 10:
            pass  # no 3.10 specific conditional opcodes

        return _conditional_se(opcode, arg, jump)
