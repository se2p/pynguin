#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
# Idea and structure are taken from the pyChecco project, see:
# https://github.com/ipsw1/pychecco
# ruff: noqa: E501, ERA001

import sys

from bytecode.instr import BinaryOp
from bytecode.instr import CellVar
from bytecode.instr import Compare
from bytecode.instr import FreeVar

from tests.slicer.util import TracedInstr
from tests.slicer.util import assert_slice_equal
from tests.slicer.util import dummy_code_object
from tests.slicer.util import slice_function_at_return
from tests.slicer.util import slice_function_at_return_with_result
from tests.slicer.util import slice_module_at_return


if sys.version_info >= (3, 12):
    inplace_add_instruction = TracedInstr("BINARY_OP", arg=BinaryOp.INPLACE_ADD.value)
    binary_add_instruction = TracedInstr("BINARY_OP", arg=BinaryOp.ADD.value)
    jump_backward_absolute = "JUMP_BACKWARD"
    pop_jump_forward_if_true = "POP_JUMP_IF_TRUE"
    pop_jump_forward_if_false = "POP_JUMP_IF_FALSE"
    end_for = TracedInstr("END_FOR")
    return_none = (TracedInstr("RETURN_CONST", arg=None),)
elif sys.version_info >= (3, 11):
    inplace_add_instruction = TracedInstr("BINARY_OP", arg=BinaryOp.INPLACE_ADD.value)
    binary_add_instruction = TracedInstr("BINARY_OP", arg=BinaryOp.ADD.value)
    jump_backward_absolute = "JUMP_BACKWARD"
    pop_jump_forward_if_true = "POP_JUMP_FORWARD_IF_TRUE"
    pop_jump_forward_if_false = "POP_JUMP_FORWARD_IF_FALSE"
    end_for = TracedInstr("NOP")
    return_none = (
        TracedInstr("LOAD_CONST", arg=None),
        TracedInstr("RETURN_VALUE"),
    )
else:
    inplace_add_instruction = TracedInstr("INPLACE_ADD")
    binary_add_instruction = TracedInstr("BINARY_ADD")
    jump_backward_absolute = "JUMP_ABSOLUTE"
    pop_jump_forward_if_true = "POP_JUMP_IF_TRUE"
    pop_jump_forward_if_false = "POP_JUMP_IF_FALSE"
    end_for = TracedInstr("NOP")
    return_none = (
        TracedInstr("LOAD_CONST", arg=None),
        TracedInstr("RETURN_VALUE"),
    )


def test_simple_loop():
    def func():
        result = 0
        for i in range(0, 3):  # noqa: PIE808
            result += i
        return result

    if sys.version_info >= (3, 12):
        range_call = (
            TracedInstr("LOAD_GLOBAL", arg=(True, "range")),
            TracedInstr("LOAD_CONST", arg=0),
            TracedInstr("LOAD_CONST", arg=3),
            TracedInstr("CALL", arg=2),
        )
    elif sys.version_info >= (3, 11):
        range_call = (
            TracedInstr("LOAD_GLOBAL", arg=(True, "range")),
            TracedInstr("LOAD_CONST", arg=0),
            TracedInstr("LOAD_CONST", arg=3),
            TracedInstr("PRECALL", arg=2),
            TracedInstr("CALL", arg=2),
        )
    else:
        range_call = (
            TracedInstr("LOAD_GLOBAL", arg="range"),
            TracedInstr("LOAD_CONST", arg=0),
            TracedInstr("LOAD_CONST", arg=3),
            TracedInstr("CALL_FUNCTION", arg=2),
        )

    expected_instructions = [
        # result = 0
        TracedInstr("LOAD_CONST", arg=0),
        TracedInstr("STORE_FAST", arg="result"),
        # for i in range(0, 3):
        *range_call,
        TracedInstr("GET_ITER"),
        TracedInstr(
            "FOR_ITER",
            # the first instruction of the return block
            arg=end_for,
        ),
        TracedInstr("STORE_FAST", arg="i"),
        # result += i
        TracedInstr("LOAD_FAST", arg="result"),
        TracedInstr("LOAD_FAST", arg="i"),
        inplace_add_instruction,
        TracedInstr("STORE_FAST", arg="result"),
        TracedInstr(
            jump_backward_absolute,
            # the loop header
            arg=TracedInstr("FOR_ITER", arg=end_for),
        ),
        # return result
        TracedInstr("LOAD_FAST", arg="result"),
        TracedInstr("RETURN_VALUE"),
    ]

    sliced_instructions = slice_function_at_return(func)
    assert_slice_equal(sliced_instructions, expected_instructions)


def test_call_without_arguments():
    if sys.version_info >= (3, 12):
        create_callee = (
            TracedInstr("LOAD_CONST", arg=dummy_code_object),
            TracedInstr("MAKE_FUNCTION", arg=0),
        )
        call_callee = (
            TracedInstr("LOAD_GLOBAL", arg=(True, "callee")),
            TracedInstr("CALL", arg=0),
        )
        return_zero = (TracedInstr("RETURN_CONST", arg=0),)
    elif sys.version_info >= (3, 11):
        create_callee = (
            TracedInstr("LOAD_CONST", arg=dummy_code_object),
            TracedInstr("MAKE_FUNCTION", arg=0),
        )
        call_callee = (
            TracedInstr("LOAD_GLOBAL", arg=(True, "callee")),
            TracedInstr("PRECALL", arg=0),
            TracedInstr("CALL", arg=0),
        )
        return_zero = (
            TracedInstr("LOAD_CONST", arg=0),
            TracedInstr("RETURN_VALUE"),
        )
    else:
        create_callee = (
            TracedInstr("LOAD_CONST", arg=dummy_code_object),
            TracedInstr("LOAD_CONST", arg="callee"),
            TracedInstr("MAKE_FUNCTION", arg=0),
        )
        call_callee = (
            TracedInstr("LOAD_GLOBAL", arg="callee"),
            TracedInstr("CALL_FUNCTION", arg=0),
        )
        return_zero = (
            TracedInstr("LOAD_CONST", arg=0),
            TracedInstr("RETURN_VALUE"),
        )

    expected_instructions = [
        # def callee():
        *create_callee,
        TracedInstr("STORE_NAME", arg="callee"),
        # ... = callee()
        *call_callee,
        # return 0
        *return_zero,
        # result = ...
        TracedInstr("STORE_FAST", arg="result"),
        # return result
        TracedInstr("LOAD_FAST", arg="result"),
        TracedInstr("RETURN_VALUE"),
    ]

    module = "tests.fixtures.slicer.simple_call"
    sliced_instructions = slice_module_at_return(module)
    assert_slice_equal(sliced_instructions, expected_instructions)


def test_call_with_arguments():
    # Call with two arguments, one of which is used in the callee
    if sys.version_info >= (3, 12):
        create_callee = (
            TracedInstr("LOAD_CONST", arg=dummy_code_object),
            TracedInstr("MAKE_FUNCTION", arg=4),
        )
        call_callee = (
            TracedInstr("LOAD_GLOBAL", arg=(True, "callee")),
            TracedInstr("LOAD_FAST", arg="foo"),
            TracedInstr("LOAD_FAST", arg="bar"),
            TracedInstr("CALL", arg=2),
        )
    elif sys.version_info >= (3, 11):
        create_callee = (
            TracedInstr("LOAD_CONST", arg=dummy_code_object),
            TracedInstr("MAKE_FUNCTION", arg=4),
        )
        call_callee = (
            TracedInstr("LOAD_GLOBAL", arg=(True, "callee")),
            TracedInstr("LOAD_FAST", arg="foo"),
            TracedInstr("LOAD_FAST", arg="bar"),
            TracedInstr("PRECALL", arg=2),
            TracedInstr("CALL", arg=2),
        )
    else:
        create_callee = (
            TracedInstr("LOAD_CONST", arg=dummy_code_object),
            TracedInstr("LOAD_CONST", arg="callee"),
            TracedInstr("MAKE_FUNCTION", arg=4),
        )
        call_callee = (
            TracedInstr("LOAD_GLOBAL", arg="callee"),
            TracedInstr("LOAD_FAST", arg="foo"),
            TracedInstr("LOAD_FAST", arg="bar"),
            TracedInstr("CALL_FUNCTION", arg=2),
        )

    expected_instructions = [
        # def callee(a: int, b: int):
        TracedInstr("LOAD_CONST", arg="a"),
        TracedInstr("LOAD_NAME", arg="int"),
        TracedInstr("LOAD_CONST", arg="b"),
        TracedInstr("LOAD_NAME", arg="int"),
        TracedInstr("BUILD_TUPLE", arg=4),
        *create_callee,
        TracedInstr("STORE_NAME", arg="callee"),
        # foo = 1
        TracedInstr("LOAD_CONST", arg=1),
        TracedInstr("STORE_FAST", arg="foo"),
        # bar = 2
        TracedInstr("LOAD_CONST", arg=2),
        TracedInstr("STORE_FAST", arg="bar"),
        # ... = callee(foo, bar)
        *call_callee,
        # return a
        TracedInstr("LOAD_FAST", arg="a"),
        TracedInstr("RETURN_VALUE"),
        # result = ...
        TracedInstr("STORE_FAST", arg="result"),
        # return result
        TracedInstr("LOAD_FAST", arg="result"),
        TracedInstr("RETURN_VALUE"),
    ]

    module = "tests.fixtures.slicer.simple_call_arg"
    sliced_instructions = slice_module_at_return(module)
    assert_slice_equal(sliced_instructions, expected_instructions)


def test_generators():
    # YIELD_VALUE and YIELD_FROM
    if sys.version_info >= (3, 12):
        create_abc_generator = (
            TracedInstr("LOAD_CONST", arg=dummy_code_object),
            TracedInstr("MAKE_FUNCTION", arg=0),
        )
        create_abc_xyz_generator = (
            TracedInstr("LOAD_CONST", arg=dummy_code_object),
            TracedInstr("MAKE_FUNCTION", arg=0),
        )
        call_abc_generator = (
            TracedInstr("LOAD_GLOBAL", arg=(True, "abc_generator")),
            TracedInstr("CALL", arg=0),
        )
        call_abc_xyz_generator = (
            TracedInstr("LOAD_GLOBAL", arg=(True, "abc_xyz_generator")),
            TracedInstr("CALL", arg=0),
        )
        yield_from = ()
        send = (
            TracedInstr("LOAD_CONST", arg=None),
            TracedInstr(
                "SEND",
                # the first instruction of the send target block
                arg=TracedInstr("TRY_END"),
            ),
            TracedInstr("YIELD_VALUE", arg=2),
        )
        yield_gen = TracedInstr("YIELD_VALUE", arg=1)
        second_comparison_jump = TracedInstr(
            pop_jump_forward_if_true,
            # the jump which leads back to the loop header
            arg=TracedInstr("LOAD_FAST", arg="result"),
        )
        last_jumps = (
            TracedInstr(
                jump_backward_absolute,
                # the loop header
                arg=TracedInstr("FOR_ITER", arg=end_for),
            ),
            TracedInstr(
                jump_backward_absolute,
                # the loop header
                arg=TracedInstr("FOR_ITER", arg=end_for),
            ),
        )
    elif sys.version_info >= (3, 11):
        create_abc_generator = (
            TracedInstr("LOAD_CONST", arg=dummy_code_object),
            TracedInstr("MAKE_FUNCTION", arg=0),
        )
        create_abc_xyz_generator = (
            TracedInstr("LOAD_CONST", arg=dummy_code_object),
            TracedInstr("MAKE_FUNCTION", arg=0),
        )
        call_abc_generator = (
            TracedInstr("LOAD_GLOBAL", arg=(True, "abc_generator")),
            TracedInstr("PRECALL", arg=0),
            TracedInstr("CALL", arg=0),
        )
        call_abc_xyz_generator = (
            TracedInstr("LOAD_GLOBAL", arg=(True, "abc_xyz_generator")),
            TracedInstr("PRECALL", arg=0),
            TracedInstr("CALL", arg=0),
        )
        yield_from = ()
        send = (
            TracedInstr("LOAD_CONST", arg=None),
            TracedInstr(
                "SEND",
                # the first instruction of the send target block
                arg=TracedInstr("POP_TOP"),
            ),
            TracedInstr("YIELD_VALUE"),
        )
        yield_gen = TracedInstr("YIELD_VALUE")
        second_comparison_jump = TracedInstr(
            pop_jump_forward_if_false,
            # the jump which leads back to the loop header
            arg=TracedInstr(
                jump_backward_absolute,
                # the loop header
                arg=TracedInstr("FOR_ITER", arg=end_for),
            ),
        )
        last_jumps = (
            TracedInstr(
                jump_backward_absolute,
                # the loop header
                arg=TracedInstr("FOR_ITER", arg=end_for),
            ),
        )
    else:
        create_abc_generator = (
            TracedInstr("LOAD_CONST", arg=dummy_code_object),
            TracedInstr("LOAD_CONST", arg="abc_generator"),
            TracedInstr("MAKE_FUNCTION", arg=0),
        )
        create_abc_xyz_generator = (
            TracedInstr("LOAD_CONST", arg=dummy_code_object),
            TracedInstr("LOAD_CONST", arg="abc_xyz_generator"),
            TracedInstr("MAKE_FUNCTION", arg=0),
        )
        call_abc_generator = (
            TracedInstr("LOAD_GLOBAL", arg="abc_generator"),
            TracedInstr("CALL_FUNCTION", arg=0),
        )
        call_abc_xyz_generator = (
            TracedInstr("LOAD_GLOBAL", arg="abc_xyz_generator"),
            TracedInstr("CALL_FUNCTION", arg=0),
        )
        yield_from = (
            TracedInstr("LOAD_CONST", arg=None),
            TracedInstr("YIELD_FROM"),
        )
        send = ()
        yield_gen = TracedInstr("YIELD_VALUE")
        second_comparison_jump = TracedInstr(
            pop_jump_forward_if_false,
            # the jump which leads back to the loop header
            arg=TracedInstr(
                jump_backward_absolute,
                # the loop header
                arg=TracedInstr("FOR_ITER", arg=end_for),
            ),
        )
        last_jumps = (
            TracedInstr(
                jump_backward_absolute,
                # the loop header
                arg=TracedInstr("FOR_ITER", arg=end_for),
            ),
        )

    expected_instructions = [
        # def abc_generator():
        *create_abc_generator,
        TracedInstr("STORE_NAME", arg="abc_generator"),
        # def abc_xyz_generator():
        *create_abc_xyz_generator,
        TracedInstr("STORE_NAME", arg="abc_xyz_generator"),
        # generator = abc_xyz_generator()
        *call_abc_xyz_generator,
        TracedInstr("STORE_FAST", arg="generator"),
        # result = ""
        TracedInstr("LOAD_CONST", arg=""),
        TracedInstr("STORE_FAST", arg="result"),
        # for ... in generator:
        TracedInstr("LOAD_FAST", arg="generator"),
        TracedInstr("GET_ITER"),
        TracedInstr(
            "FOR_ITER",
            # the first instruction of the return block
            arg=end_for,
        ),
        # x = "x"
        TracedInstr("LOAD_CONST", arg="x"),
        TracedInstr("STORE_FAST", arg="x"),
        # yield from abc_generator()
        *call_abc_generator,
        TracedInstr("GET_YIELD_FROM_ITER"),
        *yield_from,
        # a = "a"
        TracedInstr("LOAD_CONST", arg="a"),
        TracedInstr("STORE_FAST", arg="a"),
        # yield a
        TracedInstr("LOAD_FAST", arg="a"),
        yield_gen,
        *send,
        # for letter in ...:
        TracedInstr("STORE_FAST", arg="letter"),
        # letter == "x" or letter == "a":
        TracedInstr("LOAD_FAST", arg="letter"),
        TracedInstr("LOAD_CONST", arg="x"),
        TracedInstr("COMPARE_OP", arg=Compare.EQ),
        TracedInstr(
            pop_jump_forward_if_true,
            # the first instruction of the if block
            arg=TracedInstr("LOAD_FAST", arg="result"),
        ),
        TracedInstr("LOAD_FAST", arg="letter"),
        TracedInstr("LOAD_CONST", arg="a"),
        TracedInstr("COMPARE_OP", arg=Compare.EQ),
        second_comparison_jump,
        # result += letter
        TracedInstr("LOAD_FAST", arg="result"),
        TracedInstr("LOAD_FAST", arg="letter"),
        inplace_add_instruction,
        TracedInstr("STORE_FAST", arg="result"),
        *last_jumps,
        # yield x
        TracedInstr("LOAD_FAST", arg="x"),
        yield_gen,
        # return result
        TracedInstr("LOAD_FAST", arg="result"),
        TracedInstr("RETURN_VALUE"),
    ]
    module = "tests.fixtures.slicer.generator"
    sliced_instructions = slice_module_at_return(module)
    assert_slice_equal(sliced_instructions, expected_instructions)


def test_with_extended_arg():
    def func():
        p = [1, 2, 3, 4, 5, 6]
        unused = p  # noqa: F841
        q, r, *_, __ = p  # With extended argument

        result = q, r
        return result  # noqa: RET504

    expected_instructions = [
        # p = [1, 2, 3, 4, 5, 6]
        TracedInstr("BUILD_LIST", arg=0),
        TracedInstr("LOAD_CONST", arg=(1, 2, 3, 4, 5, 6)),
        TracedInstr("LIST_EXTEND", arg=1),
        TracedInstr("STORE_FAST", arg="p"),
        # q, r, *s, t = p
        TracedInstr("LOAD_FAST", arg="p"),
        # TracedInstr("EXTENDED_ARG", arg=1),  # EXTENDED_ARG can not be in a slice
        TracedInstr("UNPACK_EX", arg=258),
        TracedInstr("STORE_FAST", arg="q"),
        TracedInstr("STORE_FAST", arg="r"),
        # result = q
        TracedInstr("LOAD_FAST", arg="q"),
        TracedInstr("LOAD_FAST", arg="r"),
        TracedInstr("BUILD_TUPLE", arg=2),
        TracedInstr("STORE_FAST", arg="result"),
        # return result
        TracedInstr("LOAD_FAST", arg="result"),
        TracedInstr("RETURN_VALUE"),
    ]

    sliced_instructions = slice_function_at_return(func)
    assert_slice_equal(sliced_instructions, expected_instructions)


def test_nested_class():
    def func():
        # STORE_DEREF, LOAD_CLOSURE, LOAD_CLASSDEREF
        x = []

        class NestedClass:
            y = x

        class_attr = NestedClass.y

        result = class_attr
        return result  # noqa: RET504

    cellvar_x = CellVar("x")
    freevar_x = FreeVar("x")

    if sys.version_info >= (3, 12):
        create_nested_class = (
            TracedInstr("PUSH_NULL"),
            TracedInstr("LOAD_BUILD_CLASS"),
            TracedInstr("LOAD_CLOSURE", arg=cellvar_x),
            TracedInstr("BUILD_TUPLE", arg=1),
            TracedInstr("LOAD_CONST", arg=dummy_code_object),
            TracedInstr("MAKE_FUNCTION", arg=8),
            TracedInstr("LOAD_CONST", arg="NestedClass"),
            TracedInstr("CALL", arg=2),
        )
        load_class_deref = (
            TracedInstr("LOAD_LOCALS"),
            TracedInstr("LOAD_FROM_DICT_OR_DEREF", arg=freevar_x),
        )
        load_y = TracedInstr("LOAD_ATTR", arg=(False, "y"))
    elif sys.version_info >= (3, 11):
        create_nested_class = (
            TracedInstr("PUSH_NULL"),
            TracedInstr("LOAD_BUILD_CLASS"),
            TracedInstr("LOAD_CLOSURE", arg=cellvar_x),
            TracedInstr("BUILD_TUPLE", arg=1),
            TracedInstr("LOAD_CONST", arg=dummy_code_object),
            TracedInstr("MAKE_FUNCTION", arg=8),
            TracedInstr("LOAD_CONST", arg="NestedClass"),
            TracedInstr("PRECALL", arg=2),
            TracedInstr("CALL", arg=2),
        )
        load_class_deref = (TracedInstr("LOAD_CLASSDEREF", arg=freevar_x),)
        load_y = TracedInstr("LOAD_ATTR", arg="y")
    else:
        create_nested_class = (
            TracedInstr("LOAD_BUILD_CLASS"),
            TracedInstr("LOAD_CLOSURE", arg=cellvar_x),
            TracedInstr("BUILD_TUPLE", arg=1),
            TracedInstr("LOAD_CONST", arg=dummy_code_object),
            TracedInstr("LOAD_CONST", arg="NestedClass"),
            TracedInstr("MAKE_FUNCTION", arg=8),
            TracedInstr("LOAD_CONST", arg="NestedClass"),
            TracedInstr("CALL_FUNCTION", arg=2),
        )
        load_class_deref = (TracedInstr("LOAD_CLASSDEREF", arg=freevar_x),)
        load_y = TracedInstr("LOAD_ATTR", arg="y")

    expected_instructions = [
        # x = []
        TracedInstr("BUILD_LIST", arg=0),
        TracedInstr("STORE_DEREF", arg=cellvar_x),
        # class NestedClass:
        *create_nested_class,
        *load_class_deref,
        TracedInstr("STORE_NAME", arg="y"),
        *return_none,
        TracedInstr("STORE_FAST", arg="NestedClass"),
        # class_attr = NestedClass.y
        TracedInstr("LOAD_FAST", arg="NestedClass"),
        load_y,
        TracedInstr("STORE_FAST", arg="class_attr"),
        # result = class_attr
        TracedInstr("LOAD_FAST", arg="class_attr"),
        TracedInstr("STORE_FAST", arg="result"),
        # return result
        TracedInstr("LOAD_FAST", arg="result"),
        TracedInstr("RETURN_VALUE"),
    ]

    sliced_instructions = slice_function_at_return(func)
    assert_slice_equal(sliced_instructions, expected_instructions)


def test_nested_class_2():
    # Critical test to ensure that the attributes converted to variables
    # are taken from the correct scope.

    def func():
        # STORE_DEREF, LOAD_CLOSURE, LOAD_CLASSDEREF
        x1 = [1]
        x2 = [2]

        class Bar:
            foo = x1  # included!

            class Foo:
                foo = x2  # NOT included
                y = x2  # included

            y = Foo.y  # NOT included

        class_attr = Bar.foo
        class_attr2 = Bar.Foo.y

        result = class_attr + class_attr2
        return result  # noqa: RET504

    freevar_x1 = FreeVar("x1")
    freevar_x2 = FreeVar("x2")
    cellvar_x1 = CellVar("x1")
    cellvar_x2 = CellVar("x2")

    if sys.version_info >= (3, 12):
        create_foo_class = (
            TracedInstr("LOAD_LOCALS"),
            TracedInstr("LOAD_FROM_DICT_OR_DEREF", arg=freevar_x1),
            TracedInstr("STORE_NAME", arg="foo"),
            TracedInstr("PUSH_NULL"),
            TracedInstr("LOAD_BUILD_CLASS"),
            TracedInstr("LOAD_CLOSURE", arg=freevar_x2),
            TracedInstr("BUILD_TUPLE", arg=1),
            TracedInstr("LOAD_CONST", arg=dummy_code_object),
            TracedInstr("MAKE_FUNCTION", arg=8),
            TracedInstr("LOAD_CONST", arg="Foo"),
            TracedInstr("CALL", arg=2),
            TracedInstr("LOAD_LOCALS"),
            TracedInstr("LOAD_FROM_DICT_OR_DEREF", arg=freevar_x2),
            TracedInstr("STORE_NAME", arg="y"),
        )
        create_bar_class = (
            TracedInstr("PUSH_NULL"),
            TracedInstr("LOAD_BUILD_CLASS"),
            TracedInstr("LOAD_CLOSURE", arg=cellvar_x1),
            TracedInstr("LOAD_CLOSURE", arg=cellvar_x2),
            TracedInstr("BUILD_TUPLE", arg=2),
            TracedInstr("LOAD_CONST", arg=dummy_code_object),
            TracedInstr("MAKE_FUNCTION", arg=8),
            TracedInstr("LOAD_CONST", arg="Bar"),
            TracedInstr("CALL", arg=2),
            *create_foo_class,
            *return_none,
            TracedInstr("STORE_NAME", arg="Foo"),
        )
        load_foo = TracedInstr("LOAD_ATTR", arg=(False, "foo"))
        load_foo_class = TracedInstr("LOAD_ATTR", arg=(False, "Foo"))
        load_y = TracedInstr("LOAD_ATTR", arg=(False, "y"))
    elif sys.version_info >= (3, 11):
        create_foo_class = (
            TracedInstr("LOAD_CLASSDEREF", arg=freevar_x1),
            TracedInstr("STORE_NAME", arg="foo"),
            TracedInstr("PUSH_NULL"),
            TracedInstr("LOAD_BUILD_CLASS"),
            TracedInstr("LOAD_CLOSURE", arg=freevar_x2),
            TracedInstr("BUILD_TUPLE", arg=1),
            TracedInstr("LOAD_CONST", arg=dummy_code_object),
            TracedInstr("MAKE_FUNCTION", arg=8),
            TracedInstr("LOAD_CONST", arg="Foo"),
            TracedInstr("PRECALL", arg=2),
            TracedInstr("CALL", arg=2),
            TracedInstr("LOAD_CLASSDEREF", arg=freevar_x2),
            TracedInstr("STORE_NAME", arg="y"),
        )
        create_bar_class = (
            TracedInstr("PUSH_NULL"),
            TracedInstr("LOAD_BUILD_CLASS"),
            TracedInstr("LOAD_CLOSURE", arg=cellvar_x1),
            TracedInstr("LOAD_CLOSURE", arg=cellvar_x2),
            TracedInstr("BUILD_TUPLE", arg=2),
            TracedInstr("LOAD_CONST", arg=dummy_code_object),
            TracedInstr("MAKE_FUNCTION", arg=8),
            TracedInstr("LOAD_CONST", arg="Bar"),
            TracedInstr("PRECALL", arg=2),
            TracedInstr("CALL", arg=2),
            *create_foo_class,
            *return_none,
            TracedInstr("STORE_NAME", arg="Foo"),
        )
        load_foo = TracedInstr("LOAD_ATTR", arg="foo")
        load_foo_class = TracedInstr("LOAD_ATTR", arg="Foo")
        load_y = TracedInstr("LOAD_ATTR", arg="y")
    else:
        create_foo_class = (
            TracedInstr("LOAD_CLASSDEREF", arg=freevar_x1),
            TracedInstr("STORE_NAME", arg="foo"),
            TracedInstr("LOAD_BUILD_CLASS"),
            TracedInstr("LOAD_CLOSURE", arg=freevar_x2),
            TracedInstr("BUILD_TUPLE", arg=1),
            TracedInstr("LOAD_CONST", arg=dummy_code_object),
            TracedInstr("LOAD_CONST", arg="Foo"),
            TracedInstr("MAKE_FUNCTION", arg=8),
            TracedInstr("LOAD_CONST", arg="Foo"),
            TracedInstr("CALL_FUNCTION", arg=2),
            TracedInstr("LOAD_CLASSDEREF", arg=freevar_x2),
            TracedInstr("STORE_NAME", arg="y"),
        )
        create_bar_class = (
            TracedInstr("LOAD_BUILD_CLASS"),
            TracedInstr("LOAD_CLOSURE", arg=cellvar_x1),
            TracedInstr("LOAD_CLOSURE", arg=cellvar_x2),
            TracedInstr("BUILD_TUPLE", arg=2),
            TracedInstr("LOAD_CONST", arg=dummy_code_object),
            TracedInstr("LOAD_CONST", arg="Bar"),
            TracedInstr("MAKE_FUNCTION", arg=8),
            TracedInstr("LOAD_CONST", arg="Bar"),
            TracedInstr("CALL_FUNCTION", arg=2),
            *create_foo_class,
            *return_none,
            TracedInstr("STORE_NAME", arg="Foo"),
        )
        load_foo = TracedInstr("LOAD_ATTR", arg="foo")
        load_foo_class = TracedInstr("LOAD_ATTR", arg="Foo")
        load_y = TracedInstr("LOAD_ATTR", arg="y")

    expected_instructions = [
        # x1 = [1]
        TracedInstr("LOAD_CONST", arg=1),
        TracedInstr("BUILD_LIST", arg=1),
        TracedInstr("STORE_DEREF", arg=cellvar_x1),
        # x2 = [2]
        TracedInstr("LOAD_CONST", arg=2),
        TracedInstr("BUILD_LIST", arg=1),
        TracedInstr("STORE_DEREF", arg=cellvar_x2),
        # class Bar:
        *create_bar_class,
        *return_none,
        TracedInstr("STORE_FAST", arg="Bar"),
        # class_attr = Bar.y
        TracedInstr("LOAD_FAST", arg="Bar"),
        load_foo,
        TracedInstr("STORE_FAST", arg="class_attr"),
        # class_attr2 = Bar.Foo.y
        TracedInstr("LOAD_FAST", arg="Bar"),
        load_foo_class,
        load_y,
        TracedInstr("STORE_FAST", arg="class_attr2"),
        # result = class_attr + class_attr2
        TracedInstr("LOAD_FAST", arg="class_attr"),
        TracedInstr("LOAD_FAST", arg="class_attr2"),
        binary_add_instruction,
        TracedInstr("STORE_FAST", arg="result"),
        # return result
        TracedInstr("LOAD_FAST", arg="result"),
        TracedInstr("RETURN_VALUE"),
    ]

    sliced_instructions, result = slice_function_at_return_with_result(func)
    assert result == [1, 2]
    assert_slice_equal(sliced_instructions, expected_instructions)


def test_lambda():
    def func():
        x = lambda a: a + 10  # noqa: E731

        result = x(1)
        return result  # noqa: RET504

    if sys.version_info >= (3, 12):
        create_lambda = (
            TracedInstr("LOAD_CONST", arg=dummy_code_object),
            TracedInstr("MAKE_FUNCTION", arg=0),
        )
        call_lambda = (
            TracedInstr("PUSH_NULL"),
            TracedInstr("LOAD_FAST", arg="x"),
            TracedInstr("LOAD_CONST", arg=1),
            TracedInstr("CALL", arg=1),
        )
    elif sys.version_info >= (3, 11):
        create_lambda = (
            TracedInstr("LOAD_CONST", arg=dummy_code_object),
            TracedInstr("MAKE_FUNCTION", arg=0),
        )
        call_lambda = (
            TracedInstr("PUSH_NULL"),
            TracedInstr("LOAD_FAST", arg="x"),
            TracedInstr("LOAD_CONST", arg=1),
            TracedInstr("PRECALL", arg=1),
            TracedInstr("CALL", arg=1),
        )
    else:
        create_lambda = (
            TracedInstr("LOAD_CONST", arg=dummy_code_object),
            TracedInstr("LOAD_CONST", arg="test_lambda.<locals>.func.<locals>.<lambda>"),
            TracedInstr("MAKE_FUNCTION", arg=0),
        )
        call_lambda = (
            TracedInstr("LOAD_FAST", arg="x"),
            TracedInstr("LOAD_CONST", arg=1),
            TracedInstr("CALL_FUNCTION", arg=1),
        )

    expected_instructions = [
        # x = lambda a: a + 10
        *create_lambda,
        TracedInstr("STORE_FAST", arg="x"),
        # result = x(1)
        *call_lambda,
        TracedInstr("LOAD_FAST", arg="a"),
        TracedInstr("LOAD_CONST", arg=10),
        binary_add_instruction,
        TracedInstr("RETURN_VALUE"),
        TracedInstr("STORE_FAST", arg="result"),
        # return result
        TracedInstr("LOAD_FAST", arg="result"),
        TracedInstr("RETURN_VALUE"),
    ]

    sliced_instructions = slice_function_at_return(func)
    assert_slice_equal(sliced_instructions, expected_instructions)


def test_builtin_addresses():
    def func():
        test_dict = {1: "one", 2: "two"}
        # noinspection PyListCreation
        test_list = [1, 2]

        test_list.append(3)

        result = test_dict.get(1)
        return result  # noqa: RET504

    if sys.version_info >= (3, 12):
        call_get = (
            TracedInstr("LOAD_FAST", arg="test_dict"),
            TracedInstr("LOAD_ATTR", arg=(True, "get")),
            TracedInstr("LOAD_CONST", arg=1),
            TracedInstr("CALL", arg=1),
        )
    elif sys.version_info >= (3, 11):
        call_get = (
            TracedInstr("LOAD_FAST", arg="test_dict"),
            TracedInstr("LOAD_METHOD", arg="get"),
            TracedInstr("LOAD_CONST", arg=1),
            TracedInstr("PRECALL", arg=1),
            TracedInstr("CALL", arg=1),
        )
    else:
        call_get = (
            TracedInstr("LOAD_FAST", arg="test_dict"),
            TracedInstr("LOAD_METHOD", arg="get"),
            TracedInstr("LOAD_CONST", arg=1),
            TracedInstr("CALL_METHOD", arg=1),
        )

    expected_instructions = [
        # test_dict = {1: "one", 2: "two"}
        TracedInstr("LOAD_CONST", arg="one"),
        TracedInstr("LOAD_CONST", arg="two"),
        TracedInstr("LOAD_CONST", arg=(1, 2)),
        TracedInstr("BUILD_CONST_KEY_MAP", arg=2),
        TracedInstr("STORE_FAST", arg="test_dict"),
        # result = test_dict.get(1)
        *call_get,
        TracedInstr("STORE_FAST", arg="result"),
        # return result
        TracedInstr("LOAD_FAST", arg="result"),
        TracedInstr("RETURN_VALUE"),
    ]

    sliced_instructions = slice_function_at_return(func)
    assert_slice_equal(sliced_instructions, expected_instructions)


def test_data_dependency_immutable_attribute():
    # Explicit attribute dependency of immutable type
    if sys.version_info >= (3, 12):
        create_foo_class = (
            TracedInstr("PUSH_NULL"),
            TracedInstr("LOAD_BUILD_CLASS"),
            TracedInstr("LOAD_CONST", arg=dummy_code_object),
            TracedInstr("MAKE_FUNCTION", arg=0),
            TracedInstr("LOAD_CONST", arg="Foo"),
            TracedInstr("CALL", arg=2),
            TracedInstr("LOAD_CONST", arg=1),
            TracedInstr("STORE_NAME", arg="attr"),
        )
        load_attr = TracedInstr("LOAD_ATTR", arg=(False, "attr"))
    elif sys.version_info >= (3, 11):
        create_foo_class = (
            TracedInstr("PUSH_NULL"),
            TracedInstr("LOAD_BUILD_CLASS"),
            TracedInstr("LOAD_CONST", arg=dummy_code_object),
            TracedInstr("MAKE_FUNCTION", arg=0),
            TracedInstr("LOAD_CONST", arg="Foo"),
            TracedInstr("PRECALL", arg=2),
            TracedInstr("CALL", arg=2),
            TracedInstr("LOAD_CONST", arg=1),
            TracedInstr("STORE_NAME", arg="attr"),
        )
        load_attr = TracedInstr("LOAD_ATTR", arg="attr")
    else:
        create_foo_class = (
            TracedInstr("LOAD_BUILD_CLASS"),
            TracedInstr("LOAD_CONST", arg=dummy_code_object),
            TracedInstr("LOAD_CONST", arg="Foo"),
            TracedInstr("MAKE_FUNCTION", arg=0),
            TracedInstr("LOAD_CONST", arg="Foo"),
            TracedInstr("CALL_FUNCTION", arg=2),
            TracedInstr("LOAD_CONST", arg=1),
            TracedInstr("STORE_NAME", arg="attr"),
        )
        load_attr = TracedInstr("LOAD_ATTR", arg="attr")

    expected_instructions = [
        # class Foo:
        *create_foo_class,
        *return_none,
        TracedInstr("STORE_NAME", arg="Foo"),
        # result = ob.attr
        TracedInstr("LOAD_FAST", arg="ob"),
        load_attr,
        TracedInstr("STORE_FAST", arg="result"),
        # return result
        TracedInstr("LOAD_FAST", arg="result"),
        TracedInstr("RETURN_VALUE"),
    ]

    module = "tests.fixtures.slicer.immutable_attribute_dependency"
    sliced_instructions = slice_module_at_return(module)
    assert_slice_equal(sliced_instructions, expected_instructions)


def test_object_modification_call():
    def func():
        class NestedClass:
            def __init__(self):
                self.x = 1

            def inc_x(self):
                self.x = self.x + 1  # noqa: PLR6104

        ob = NestedClass()
        ob.inc_x()

        result = ob.x
        return result  # noqa: RET504

    if sys.version_info >= (3, 12):
        create_nested_class = (
            TracedInstr("PUSH_NULL"),
            TracedInstr("LOAD_BUILD_CLASS"),
            TracedInstr("LOAD_CONST", arg=dummy_code_object),
            TracedInstr("MAKE_FUNCTION", arg=0),
            TracedInstr("LOAD_CONST", arg="NestedClass"),
            TracedInstr("CALL", arg=2),
            TracedInstr("LOAD_CONST", arg=dummy_code_object),
            TracedInstr("MAKE_FUNCTION", arg=0),
            TracedInstr("STORE_NAME", arg="inc_x"),
        )
        call_nested_class = (
            TracedInstr("PUSH_NULL"),
            TracedInstr("LOAD_FAST", arg="NestedClass"),
            TracedInstr("CALL", arg=0),
        )
        call_inc_x_method = (
            TracedInstr("LOAD_FAST", arg="ob"),
            TracedInstr("LOAD_ATTR", arg=(True, "inc_x")),
            TracedInstr("CALL", arg=0),
        )
        load_x = TracedInstr("LOAD_ATTR", arg=(False, "x"))
    elif sys.version_info >= (3, 11):
        create_nested_class = (
            TracedInstr("PUSH_NULL"),
            TracedInstr("LOAD_BUILD_CLASS"),
            TracedInstr("LOAD_CONST", arg=dummy_code_object),
            TracedInstr("MAKE_FUNCTION", arg=0),
            TracedInstr("LOAD_CONST", arg="NestedClass"),
            TracedInstr("PRECALL", arg=2),
            TracedInstr("CALL", arg=2),
            TracedInstr("LOAD_CONST", arg=dummy_code_object),
            TracedInstr("MAKE_FUNCTION", arg=0),
            TracedInstr("STORE_NAME", arg="inc_x"),
        )
        call_nested_class = (
            TracedInstr("PUSH_NULL"),
            TracedInstr("LOAD_FAST", arg="NestedClass"),
            TracedInstr("PRECALL", arg=0),
            TracedInstr("CALL", arg=0),
        )
        call_inc_x_method = (
            TracedInstr("LOAD_FAST", arg="ob"),
            TracedInstr("LOAD_METHOD", arg="inc_x"),
            TracedInstr("PRECALL", arg=0),
            TracedInstr("CALL", arg=0),
        )
        load_x = TracedInstr("LOAD_ATTR", arg="x")
    else:
        create_nested_class = (
            TracedInstr("LOAD_BUILD_CLASS"),
            TracedInstr("LOAD_CONST", arg=dummy_code_object),
            TracedInstr("LOAD_CONST", arg="NestedClass"),
            TracedInstr("MAKE_FUNCTION", arg=0),
            TracedInstr("LOAD_CONST", arg="NestedClass"),
            TracedInstr("CALL_FUNCTION", arg=2),
            # Definition of dunder methods are wrongly excluded, since these are not explicitly loaded
            # def __init__(self):
            # TracedInstr("LOAD_CONST", arg=dummy_code_object),
            # TracedInstr("LOAD_CONST", arg="IntegrationTestLanguageFeatures.test_object_modification_call.<locals>."
            #                         "func.<locals>.NestedClass.__init__"),
            # TracedInstr("MAKE_FUNCTION", arg=0),
            # TracedInstr("STORE_NAME", arg="__init__"),
            # def inc_x(self):
            TracedInstr("LOAD_CONST", arg=dummy_code_object),
            TracedInstr(
                "LOAD_CONST",
                arg="test_object_modification_call.<locals>.func.<locals>.NestedClass.inc_x",
            ),
            TracedInstr("MAKE_FUNCTION", arg=0),
            TracedInstr("STORE_NAME", arg="inc_x"),
        )
        call_nested_class = (
            TracedInstr("LOAD_FAST", arg="NestedClass"),
            TracedInstr("CALL_FUNCTION", arg=0),
        )
        call_inc_x_method = (
            TracedInstr("LOAD_FAST", arg="ob"),
            TracedInstr("LOAD_METHOD", arg="inc_x"),
            TracedInstr("CALL_METHOD", arg=0),
        )
        load_x = TracedInstr("LOAD_ATTR", arg="x")

    expected_instructions = [
        # class NestedClass:
        *create_nested_class,
        *return_none,
        TracedInstr("STORE_FAST", arg="NestedClass"),
        # ob = NestedClass()
        *call_nested_class,
        TracedInstr("LOAD_CONST", arg=1),
        TracedInstr("LOAD_FAST", arg="self"),
        TracedInstr("STORE_ATTR", arg="x"),
        *return_none,
        TracedInstr("STORE_FAST", arg="ob"),
        # ob.inc_x()
        *call_inc_x_method,
        TracedInstr("LOAD_FAST", arg="self"),
        load_x,
        TracedInstr("LOAD_CONST", arg=1),
        binary_add_instruction,
        TracedInstr("LOAD_FAST", arg="self"),
        TracedInstr("STORE_ATTR", arg="x"),
        # result = ob.x
        TracedInstr("LOAD_FAST", arg="ob"),
        load_x,
        TracedInstr("STORE_FAST", arg="result"),
        # return result
        TracedInstr("LOAD_FAST", arg="result"),
        TracedInstr("RETURN_VALUE"),
    ]

    sliced_instructions = slice_function_at_return(func)
    assert_slice_equal(sliced_instructions, expected_instructions)


def test_closures():
    # Closure function

    freevar_foo = FreeVar("foo")
    cellvar_foo = CellVar("foo")

    if sys.version_info >= (3, 12):
        create_outer_function = (
            TracedInstr("LOAD_CONST", arg=dummy_code_object),
            TracedInstr("MAKE_FUNCTION", arg=0),
        )
        call_outer_function = (
            TracedInstr("LOAD_GLOBAL", arg=(True, "outer_function")),
            TracedInstr("LOAD_CONST", arg="a"),
            TracedInstr("CALL", arg=1),
        )
        create_inner_function = (
            TracedInstr("LOAD_CLOSURE", arg=cellvar_foo),
            TracedInstr("BUILD_TUPLE", arg=1),
            TracedInstr("LOAD_CONST", arg=dummy_code_object),
            TracedInstr("MAKE_FUNCTION", arg=8),
        )
        call_inner_function = (
            TracedInstr("PUSH_NULL"),
            TracedInstr("LOAD_FAST", arg="inner"),
            TracedInstr("LOAD_CONST", arg="abc"),
            TracedInstr("CALL", arg=1),
        )
    elif sys.version_info >= (3, 11):
        create_outer_function = (
            TracedInstr("LOAD_CONST", arg=dummy_code_object),
            TracedInstr("MAKE_FUNCTION", arg=0),
        )
        call_outer_function = (
            TracedInstr("LOAD_GLOBAL", arg=(True, "outer_function")),
            TracedInstr("LOAD_CONST", arg="a"),
            TracedInstr("PRECALL", arg=1),
            TracedInstr("CALL", arg=1),
        )
        create_inner_function = (
            TracedInstr("LOAD_CLOSURE", arg=cellvar_foo),
            TracedInstr("BUILD_TUPLE", arg=1),
            TracedInstr("LOAD_CONST", arg=dummy_code_object),
            TracedInstr("MAKE_FUNCTION", arg=8),
        )
        call_inner_function = (
            TracedInstr("PUSH_NULL"),
            TracedInstr("LOAD_FAST", arg="inner"),
            TracedInstr("LOAD_CONST", arg="abc"),
            TracedInstr("PRECALL", arg=1),
            TracedInstr("CALL", arg=1),
        )
    else:
        create_outer_function = (
            TracedInstr("LOAD_CONST", arg=dummy_code_object),
            TracedInstr("LOAD_CONST", arg="outer_function"),
            TracedInstr("MAKE_FUNCTION", arg=0),
        )
        call_outer_function = (
            TracedInstr("LOAD_GLOBAL", arg="outer_function"),
            TracedInstr("LOAD_CONST", arg="a"),
            TracedInstr("CALL_FUNCTION", arg=1),
        )
        create_inner_function = (
            TracedInstr("LOAD_CLOSURE", arg=cellvar_foo),
            TracedInstr("BUILD_TUPLE", arg=1),
            TracedInstr("LOAD_CONST", arg=dummy_code_object),
            TracedInstr("LOAD_CONST", arg="outer_function.<locals>.inner_function"),
            TracedInstr("MAKE_FUNCTION", arg=8),
        )
        call_inner_function = (
            TracedInstr("LOAD_FAST", arg="inner"),
            TracedInstr("LOAD_CONST", arg="abc"),
            TracedInstr("CALL_FUNCTION", arg=1),
        )

    expected_instructions = [
        # def outer_function(foo):
        *create_outer_function,
        TracedInstr("STORE_NAME", arg="outer_function"),
        # ... = outer_function("a")
        *call_outer_function,
        # def inner_function(bar):
        *create_inner_function,
        TracedInstr("STORE_FAST", arg="inner_function"),
        # return inner_function
        TracedInstr("LOAD_FAST", arg="inner_function"),
        TracedInstr("RETURN_VALUE"),
        # inner = ...
        TracedInstr("STORE_FAST", arg="inner"),
        # ... = inner("abc")
        *call_inner_function,
        # return foo in bar
        TracedInstr("LOAD_DEREF", arg=freevar_foo),
        TracedInstr("LOAD_FAST", arg="bar"),
        TracedInstr("CONTAINS_OP", arg=0),
        TracedInstr("RETURN_VALUE"),
        # result = ...
        TracedInstr("STORE_FAST", arg="result"),
        # return result
        TracedInstr("LOAD_FAST", arg="result"),
        TracedInstr("RETURN_VALUE"),
    ]

    module = "tests.fixtures.slicer.closure"
    sliced_instructions = slice_module_at_return(module)
    assert_slice_equal(sliced_instructions, expected_instructions)
