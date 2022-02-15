#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
# Idea and structure are taken from the pyChecco project, see:
# https://github.com/ipsw1/pychecco
"""Provides offset calculations for stack effects"""

from typing import Tuple

from opcode import opmap, opname

import pynguin.utils.opcodes as op
from pynguin.utils.exceptions import UncertainStackEffectException


# pylint:disable=too-few-public-methods.
class _SE:
    """Stack effects in python 3.8
    Stack effects are should match the combined effects in the CPython interpreter:
    https://github.com/python/cpython/blob/3.8/Python/compile.c#L999
    """

    NOP = 0, 0
    EXTENDED_ARG = 0, 0

    # Stack manipulation
    POP_TOP = 1, 0
    ROT_TWO = 2, 2
    ROT_THREE = 3, 3
    ROT_FOUR = 4, 4
    DUP_TOP = 1, 2
    DUP_TOP_TWO = 2, 4

    UNARY_POSITIVE = UNARY_NEGATIVE = UNARY_NOT = UNARY_INVERT = 1, 1

    SET_ADD = 2, 1
    LIST_APPEND = 1, 0
    MAP_ADD = 2, 0

    BINARY_POWER = (
        BINARY_MULTIPLY
    ) = (
        BINARY_MATRIX_MULTIPLY
    ) = (
        BINARY_MODULO
    ) = (
        BINARY_ADD
    ) = BINARY_SUBTRACT = BINARY_SUBSCR = BINARY_FLOOR_DIVIDE = BINARY_TRUE_DIVIDE = (
        2,
        1,
    )

    INPLACE_FLOOR_DIVIDE = INPLACE_TRUE_DIVIDE = 2, 1

    INPLACE_ADD = (
        INPLACE_SUBTRACT
    ) = INPLACE_MULTIPLY = INPLACE_MATRIX_MULTIPLY = INPLACE_MODULO = (2, 1)
    STORE_SUBSCR = 3, 0
    DELETE_SUBSCR = 2, 0

    BINARY_LSHIFT = BINARY_RSHIFT = BINARY_AND = BINARY_XOR = BINARY_OR = 2, 1
    INPLACE_POWER = 2, 1
    GET_ITER = 1, 1

    PRINT_EXPR = 1, 0
    LOAD_BUILD_CLASS = 0, 1
    INPLACE_LSHIFT = INPLACE_RSHIFT = INPLACE_AND = INPLACE_XOR = INPLACE_OR = 2, 1

    RETURN_VALUE = 1, 0
    IMPORT_STAR = 1, 0
    SETUP_ANNOTATIONS = 0, 0
    YIELD_VALUE = 1, 1
    YIELD_FROM = 2, 1
    POP_BLOCK = 0, 0
    POP_EXCEPT = 3, 0
    POP_FINALLY = END_FINALLY = 6, 0

    STORE_NAME = 1, 0
    DELETE_NAME = 0, 0

    STORE_ATTR = 2, 0
    DELETE_ATTR = 1, 0
    STORE_GLOBAL = 1, 0
    DELETE_GLOBAL = 0, 0
    LOAD_CONST = 0, 1
    LOAD_NAME = 0, 1
    LOAD_ATTR = 1, 1
    COMPARE_OP = 2, 1
    IMPORT_NAME = 2, 1
    IMPORT_FROM = 0, 1
    # 1, 2 would be more accurate, but this would cause a wider scope;
    # we compensate this by treating IMPORT_NAME as a definition
    # -> connection is made via module memory address

    JUMP_FORWARD = 0, 0
    JUMP_ABSOLUTE = 0, 0

    POP_JUMP_IF_FALSE = 1, 0
    POP_JUMP_IF_TRUE = 1, 0

    LOAD_GLOBAL = 0, 1

    BEGIN_FINALLY = 0, 6

    LOAD_FAST = 0, 1
    STORE_FAST = 1, 0
    DELETE_FAST = 0, 0

    LOAD_CLOSURE = 0, 1
    LOAD_DEREF = LOAD_CLASSDEREF = 0, 1
    STORE_DEREF = 1, 0
    DELETE_DEREF = 0, 0

    GET_AWAITABLE = 1, 1
    BEFORE_ASYNC_WITH = 1, 2
    GET_AITER = 1, 1
    GET_ANEXT = 1, 2
    GET_YIELD_FROM_ITER = 1, 1

    LOAD_METHOD = 1, 2


class StackEffect:
    """Utility class for all stack effect calculations."""

    UNCERTAIN = [
        op.WITH_CLEANUP_START,
        op.WITH_CLEANUP_FINISH,
        op.SETUP_ASYNC_WITH,
        op.END_ASYNC_FOR,
        op.FORMAT_VALUE,
    ]
    STACK_MANIPULATION = [
        op.ROT_TWO,
        op.ROT_THREE,
        op.ROT_FOUR,
        op.DUP_TOP,
        op.DUP_TOP_TWO,
    ]
    BUILD = [op.BUILD_TUPLE, op.BUILD_LIST, op.BUILD_SET, op.BUILD_STRING]
    UNPACK = [
        op.BUILD_LIST_UNPACK,
        op.BUILD_TUPLE_UNPACK,
        op.BUILD_TUPLE_UNPACK_WITH_CALL,
        op.BUILD_SET_UNPACK,
        op.BUILD_MAP_UNPACK,
        op.BUILD_MAP_UNPACK_WITH_CALL,
    ]

    # lookup method for python3.8
    _se = dict((opmap.get(op), getattr(_SE, op)) for op in opname if hasattr(_SE, op))

    # pylint: disable=too-many-branches, too-many-return-statements
    @staticmethod
    def stack_effect(opcode: int, arg, jump: bool) -> Tuple[int, int]:  # noqa: C901
        """Get the stack effect for an opcode."""
        if opcode in StackEffect.UNCERTAIN:
            raise UncertainStackEffectException(
                "The opname " + str(opcode) + " has a special flow control"
            )

        # Static stack effect
        if opcode in StackEffect._se:
            return StackEffect._se[opcode]

        # Instructions depending on jump
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
        if opcode == op.CALL_FINALLY:
            if not jump:
                return 0, 1
            return 0, 0

        # Instructions depending on argument
        if opcode == op.UNPACK_SEQUENCE:
            return 1, arg
        if opcode == op.UNPACK_EX:
            return 1, (arg & 0xFF) + (arg >> 8) + 1
        if opcode in StackEffect.BUILD:
            return arg, 1
        if opcode in StackEffect.UNPACK:
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

        raise ValueError("The opcode " + str(opcode) + " isn't recognized.")
