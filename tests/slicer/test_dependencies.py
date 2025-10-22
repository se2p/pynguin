#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
# Idea and structure are taken from the pyChecco project, see:
# https://github.com/ipsw1/pychecco
# ruff: noqa: ERA001
import dis
import sys

from bytecode.instr import BinaryOp
from bytecode.instr import Compare

from tests.slicer.util import TracedInstr
from tests.slicer.util import assert_slice_equal
from tests.slicer.util import dummy_code_object
from tests.slicer.util import slice_function_at_return
from tests.slicer.util import slice_module_at_return


if sys.version_info >= (3, 14):
    add_instr = TracedInstr("BINARY_OP", arg=BinaryOp.ADD.value)
    create_foo_class = (
        TracedInstr("LOAD_BUILD_CLASS"),
        TracedInstr("PUSH_NULL"),
        TracedInstr("LOAD_CONST", arg=dummy_code_object),
        TracedInstr("MAKE_FUNCTION"),
        TracedInstr("LOAD_CONST", arg="Foo"),
        TracedInstr("CALL", arg=2),
    )
    pop_jump_if_false = "POP_JUMP_IF_FALSE"
    return_none = (TracedInstr("LOAD_CONST", arg=None), TracedInstr("RETURN_VALUE"))
    eq_compare = Compare.EQ_CAST
    load_const = "LOAD_SMALL_INT"
    load_fast = "LOAD_FAST_BORROW"
elif sys.version_info >= (3, 13):
    add_instr = TracedInstr("BINARY_OP", arg=BinaryOp.ADD.value)
    create_foo_class = (
        TracedInstr("LOAD_BUILD_CLASS"),
        TracedInstr("PUSH_NULL"),
        TracedInstr("LOAD_CONST", arg=dummy_code_object),
        TracedInstr("MAKE_FUNCTION"),
        TracedInstr("LOAD_CONST", arg="Foo"),
        TracedInstr("CALL", arg=2),
    )
    pop_jump_if_false = "POP_JUMP_IF_FALSE"
    return_none = (TracedInstr("RETURN_CONST", arg=None),)
    eq_compare = Compare.EQ_CAST
    load_const = "LOAD_CONST"
    load_fast = "LOAD_FAST"
elif sys.version_info >= (3, 12):
    add_instr = TracedInstr("BINARY_OP", arg=BinaryOp.ADD.value)
    create_foo_class = (
        TracedInstr("PUSH_NULL"),
        TracedInstr("LOAD_BUILD_CLASS"),
        TracedInstr("LOAD_CONST", arg=dummy_code_object),
        TracedInstr("MAKE_FUNCTION", arg=0),
        TracedInstr("LOAD_CONST", arg="Foo"),
        TracedInstr("CALL", arg=2),
    )
    pop_jump_if_false = "POP_JUMP_IF_FALSE"
    return_none = (TracedInstr("RETURN_CONST", arg=None),)
    eq_compare = Compare.EQ
    load_const = "LOAD_CONST"
    load_fast = "LOAD_FAST"
elif sys.version_info >= (3, 11):
    add_instr = TracedInstr("BINARY_OP", arg=BinaryOp.ADD.value)
    create_foo_class = (
        TracedInstr("PUSH_NULL"),
        TracedInstr("LOAD_BUILD_CLASS"),
        TracedInstr("LOAD_CONST", arg=dummy_code_object),
        TracedInstr("MAKE_FUNCTION", arg=0),
        TracedInstr("LOAD_CONST", arg="Foo"),
        TracedInstr("PRECALL", arg=2),
        TracedInstr("CALL", arg=2),
    )
    pop_jump_if_false = "POP_JUMP_FORWARD_IF_FALSE"
    return_none = (
        TracedInstr("LOAD_CONST", arg=None),
        TracedInstr("RETURN_VALUE"),
    )
    eq_compare = Compare.EQ
    load_const = "LOAD_CONST"
    load_fast = "LOAD_FAST"
else:
    add_instr = TracedInstr("BINARY_ADD")
    create_foo_class = (
        TracedInstr("LOAD_BUILD_CLASS"),
        TracedInstr("LOAD_CONST", arg=dummy_code_object),
        TracedInstr("LOAD_CONST", arg="Foo"),
        TracedInstr("MAKE_FUNCTION", arg=0),
        TracedInstr("LOAD_CONST", arg="Foo"),
        TracedInstr("CALL_FUNCTION", arg=2),
    )
    pop_jump_if_false = "POP_JUMP_IF_FALSE"
    return_none = (
        TracedInstr("LOAD_CONST", arg=None),
        TracedInstr("RETURN_VALUE"),
    )
    eq_compare = Compare.EQ
    load_const = "LOAD_CONST"
    load_fast = "LOAD_FAST"


def test_data_dependency_1():
    # Implicit data dependency at return, explicit (full cover) for result
    def func() -> int:
        result = 1
        return result  # noqa: RET504

    expected_instructions = [
        # result = 1
        TracedInstr(load_const, arg=1),
        TracedInstr("STORE_FAST", arg="result"),
        # return result
        TracedInstr(load_fast, arg="result"),
        TracedInstr("RETURN_VALUE"),
    ]

    sliced_instructions = slice_function_at_return(func)
    assert_slice_equal(sliced_instructions, expected_instructions)


def test_data_dependency_2():
    # Implicit data dependency at return, explicit (full cover) for result;
    # foo must be excluded
    def func() -> int:
        result = 1
        foo = 2  # noqa: F841
        return result

    expected_instructions = [
        # result = 1
        TracedInstr(load_const, arg=1),
        TracedInstr("STORE_FAST", arg="result"),
        # return result
        TracedInstr(load_fast, arg="result"),
        TracedInstr("RETURN_VALUE"),
    ]

    sliced_instructions = slice_function_at_return(func)
    assert_slice_equal(sliced_instructions, expected_instructions)


def test_data_dependency_3():
    # Transitive explicit (full cover) dependencies
    def func() -> int:
        foo = 1
        result = 1 + foo
        return result  # noqa: RET504

    expected_instructions = [
        # foo = 1
        TracedInstr(load_const, arg=1),
        TracedInstr("STORE_FAST", arg="foo"),
        # result = 1 + foo
        TracedInstr(load_const, arg=1),
        TracedInstr(load_fast, arg="foo"),
        add_instr,
        TracedInstr("STORE_FAST", arg="result"),
        # return result
        TracedInstr(load_fast, arg="result"),
        TracedInstr("RETURN_VALUE"),
    ]

    sliced_instructions = slice_function_at_return(func)
    assert_slice_equal(sliced_instructions, expected_instructions)


def test_data_dependency_4():
    # Explicit attribute dependencies (full cover)
    if sys.version_info >= (3, 12):
        attr1 = (False, "attr1")
        attr2 = (False, "attr2")
    else:
        attr1 = "attr1"
        attr2 = "attr2"

    expected_instructions = [
        # class Foo:
        *create_foo_class,
        TracedInstr("BUILD_LIST", arg=0),
        TracedInstr("LOAD_CONST", arg=(1, 2, 3)),
        TracedInstr("LIST_EXTEND", arg=1),
        TracedInstr("STORE_NAME", arg="attr2"),
        *return_none,
        TracedInstr("STORE_NAME", arg="Foo"),
        # ob.attr1 = 1
        TracedInstr(load_const, arg=1),
        TracedInstr(load_fast, arg="ob"),
        TracedInstr("STORE_ATTR", arg="attr1"),
        # ob.attr2 = ob.attr2 + [ob.attr1]
        TracedInstr(load_fast, arg="ob"),
        TracedInstr("LOAD_ATTR", arg=attr2),
        TracedInstr(load_fast, arg="ob"),
        TracedInstr("LOAD_ATTR", arg=attr1),
        TracedInstr("BUILD_LIST", arg=1),
        add_instr,
        TracedInstr(load_fast, arg="ob"),
        TracedInstr("STORE_ATTR", arg="attr2"),
        # result = ob.attr2
        TracedInstr(load_fast, arg="ob"),
        TracedInstr("LOAD_ATTR", arg=attr2),
        TracedInstr("STORE_FAST", arg="result"),
        # return result
        TracedInstr(load_fast, arg="result"),
        TracedInstr("RETURN_VALUE"),
    ]

    module = "tests.fixtures.slicer.attribute_dependencies"
    sliced_instructions = slice_module_at_return(module)
    assert_slice_equal(sliced_instructions, expected_instructions)


def test_data_dependency_5():
    # Explicit attribute dependencies (partial and full cover)
    if sys.version_info >= (3, 12):
        instantiate_foo_class = (
            TracedInstr("LOAD_GLOBAL", arg=(True, "Foo")),
            TracedInstr("CALL", arg=0),
            TracedInstr("STORE_FAST", arg="ob"),
        )
    elif sys.version_info >= (3, 11):
        instantiate_foo_class = (
            TracedInstr("LOAD_GLOBAL", arg=(True, "Foo")),
            TracedInstr("PRECALL", arg=0),
            TracedInstr("CALL", arg=0),
            TracedInstr("STORE_FAST", arg="ob"),
        )
    else:
        instantiate_foo_class = (
            TracedInstr("LOAD_GLOBAL", arg="Foo"),
            TracedInstr("CALL_FUNCTION", arg=0),
            TracedInstr("STORE_FAST", arg="ob"),
        )

    expected_instructions = [
        # class Foo:
        *create_foo_class,
        *return_none,
        TracedInstr("STORE_NAME", arg="Foo"),
        # ob = Foo()
        *instantiate_foo_class,
        # ob.attr1 = 1
        TracedInstr(load_const, arg=1),
        TracedInstr(load_fast, arg="ob"),
        TracedInstr("STORE_ATTR", arg="attr1"),
        # result = ob
        TracedInstr("LOAD_FAST", arg="ob"),  # intentionally not LOAD_FAST_BORROW
        TracedInstr("STORE_FAST", arg="result"),
        # return result
        TracedInstr(load_fast, arg="result"),
        TracedInstr("RETURN_VALUE"),
    ]

    module = "tests.fixtures.slicer.partial_cover_dependency"
    sliced_instructions = slice_module_at_return(module)
    assert_slice_equal(sliced_instructions, expected_instructions)


def test_simple_control_dependency_1():
    # If condition evaluated to true, with relevant variable foo
    def func() -> int:  # pragma: no cover
        foo = 1
        result = 3

        if foo == 1:
            result = 1

        return result

    expected_instructions = [
        # foo = 1
        TracedInstr(load_const, arg=1),
        TracedInstr("STORE_FAST", arg="foo"),
        # if foo == 1:
        TracedInstr(load_fast, arg="foo"),
        TracedInstr(load_const, arg=1),
        TracedInstr("COMPARE_OP", arg=eq_compare),
        TracedInstr(
            pop_jump_if_false,
            # the first instruction of the return block
            arg=TracedInstr(load_fast, arg="result"),
        ),
        # result = 1
        TracedInstr(load_const, arg=1),
        TracedInstr("STORE_FAST", arg="result"),
        # return result
        TracedInstr(load_fast, arg="result"),
        TracedInstr("RETURN_VALUE"),
    ]

    sliced_instructions = slice_function_at_return(func)
    assert_slice_equal(sliced_instructions, expected_instructions)


def test_simple_control_dependency_2():
    # If condition evaluated to false, with two relevant variables (but no influence on result)
    def func() -> int:  # pragma: no cover
        foo = 1
        bar = 2
        result = 3

        if foo == bar:
            result = 1

        return result

    dis.dis(func)

    expected_instructions = [
        # result = 3
        TracedInstr(load_const, arg=3),
        TracedInstr("STORE_FAST", arg="result"),
        # return result
        TracedInstr(load_fast, arg="result"),
        TracedInstr("RETURN_VALUE"),
    ]

    sliced_instructions = slice_function_at_return(func)
    assert_slice_equal(sliced_instructions, expected_instructions)


def test_simple_control_dependency_3():
    # If-elif-else with elif branch true
    def func() -> int:  # pragma: no cover
        foo = 1
        bar = 2

        if foo == bar:
            result = 1
        elif foo == 1:
            result = 2
        else:
            result = 3

        return result

    if sys.version_info >= (3, 14):
        jump_instruction = ()
        load_foo_and_bar = (TracedInstr("LOAD_FAST_BORROW_LOAD_FAST_BORROW", arg=("foo", "bar")),)
    elif sys.version_info >= (3, 13):
        jump_instruction = ()
        load_foo_and_bar = (TracedInstr("LOAD_FAST_LOAD_FAST", arg=("foo", "bar")),)
    elif sys.version_info >= (3, 12):
        jump_instruction = ()
        load_foo_and_bar = (
            TracedInstr("LOAD_FAST", arg="foo"),
            TracedInstr("LOAD_FAST", arg="bar"),
        )
    elif sys.version_info >= (3, 11):
        jump_instruction = (
            TracedInstr(
                "JUMP_FORWARD",
                # the first instruction of the return block
                arg=TracedInstr("LOAD_FAST", arg="result"),
            ),
        )
        load_foo_and_bar = (
            TracedInstr("LOAD_FAST", arg="foo"),
            TracedInstr("LOAD_FAST", arg="bar"),
        )
    else:
        jump_instruction = ()
        load_foo_and_bar = (
            TracedInstr("LOAD_FAST", arg="foo"),
            TracedInstr("LOAD_FAST", arg="bar"),
        )

    expected_instructions = [
        # foo = 1
        TracedInstr(load_const, arg=1),
        TracedInstr("STORE_FAST", arg="foo"),
        # bar = 2
        TracedInstr(load_const, arg=2),
        TracedInstr("STORE_FAST", arg="bar"),
        # if foo == bar:
        *load_foo_and_bar,
        TracedInstr("COMPARE_OP", arg=eq_compare),
        TracedInstr(
            pop_jump_if_false,
            # the first instruction of the elif block
            arg=TracedInstr(load_fast, arg="foo"),
        ),
        # elif foo == 1:
        TracedInstr(load_fast, arg="foo"),
        TracedInstr(load_const, arg=1),
        TracedInstr("COMPARE_OP", arg=eq_compare),
        TracedInstr(
            pop_jump_if_false,
            # the first instruction of the else block
            arg=TracedInstr(load_const, arg=3),
        ),
        # result = 2
        TracedInstr(load_const, arg=2),
        TracedInstr("STORE_FAST", arg="result"),
        *jump_instruction,
        # return result
        TracedInstr(load_fast, arg="result"),
        TracedInstr("RETURN_VALUE"),
    ]

    sliced_instructions = slice_function_at_return(func)
    assert_slice_equal(sliced_instructions, expected_instructions)


def test_simple_control_dependency_4():
    # If-elif-else with else branch true
    def func() -> int:  # pragma: no cover
        foo = 1
        bar = 2

        if foo == bar:
            result = 1
        elif foo > bar:
            result = 2
        else:
            result = 3

        return result

    if sys.version_info >= (3, 14):
        load_foo_and_bar = (TracedInstr("LOAD_FAST_BORROW_LOAD_FAST_BORROW", arg=("foo", "bar")),)
        gt_compare = Compare.GT_CAST
    elif sys.version_info >= (3, 13):
        load_foo_and_bar = (TracedInstr("LOAD_FAST_LOAD_FAST", arg=("foo", "bar")),)
        gt_compare = Compare.GT_CAST
    else:
        load_foo_and_bar = (
            TracedInstr("LOAD_FAST", arg="foo"),
            TracedInstr("LOAD_FAST", arg="bar"),
        )
        gt_compare = Compare.GT

    expected_instructions = [
        # foo = 1
        TracedInstr(load_const, arg=1),
        TracedInstr("STORE_FAST", arg="foo"),
        # bar = 2
        TracedInstr(load_const, arg=2),
        TracedInstr("STORE_FAST", arg="bar"),
        # if foo == bar:
        *load_foo_and_bar,
        TracedInstr("COMPARE_OP", arg=eq_compare),
        TracedInstr(
            pop_jump_if_false,
            # the first instruction of the elif block
            arg=load_foo_and_bar[0],
        ),
        # elif foo > bar:
        *load_foo_and_bar,
        TracedInstr("COMPARE_OP", arg=gt_compare),
        TracedInstr(
            pop_jump_if_false,
            # the first instruction of the else block
            arg=TracedInstr(load_const, arg=3),
        ),
        # result = 3
        TracedInstr(load_const, arg=3),
        TracedInstr("STORE_FAST", arg="result"),
        # return result
        TracedInstr(load_fast, arg="result"),
        TracedInstr("RETURN_VALUE"),
    ]

    sliced_instructions = slice_function_at_return(func)
    assert_slice_equal(sliced_instructions, expected_instructions)
