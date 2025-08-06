#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
# Idea and structure are taken from the pyChecco project, see:
# https://github.com/ipsw1/pychecco
# ruff: noqa: ERA001

import sys

from bytecode.instr import BinaryOp
from bytecode.instr import Compare

from tests.slicer.util import TracedInstr
from tests.slicer.util import assert_slice_equal
from tests.slicer.util import dummy_code_object
from tests.slicer.util import slice_function_at_return
from tests.slicer.util import slice_module_at_return


if sys.version_info >= (3, 11):
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


def test_data_dependency_1():
    # Implicit data dependency at return, explicit (full cover) for result
    def func() -> int:
        result = 1
        return result  # noqa: RET504

    expected_instructions = [
        # result = 1
        TracedInstr("LOAD_CONST", arg=1),
        TracedInstr("STORE_FAST", arg="result"),
        # return result
        TracedInstr("LOAD_FAST", arg="result"),
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
        TracedInstr("LOAD_CONST", arg=1),
        TracedInstr("STORE_FAST", arg="result"),
        # return result
        TracedInstr("LOAD_FAST", arg="result"),
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
        TracedInstr("LOAD_CONST", arg=1),
        TracedInstr("STORE_FAST", arg="foo"),
        # result = 1 + foo
        TracedInstr("LOAD_CONST", arg=1),
        TracedInstr("LOAD_FAST", arg="foo"),
        add_instr,
        TracedInstr("STORE_FAST", arg="result"),
        # return result
        TracedInstr("LOAD_FAST", arg="result"),
        TracedInstr("RETURN_VALUE"),
    ]

    sliced_instructions = slice_function_at_return(func)
    assert_slice_equal(sliced_instructions, expected_instructions)


def test_data_dependency_4():
    # Explicit attribute dependencies (full cover)
    expected_instructions = [
        # class Foo:
        *create_foo_class,
        TracedInstr("BUILD_LIST", arg=0),
        TracedInstr("LOAD_CONST", arg=(1, 2, 3)),
        TracedInstr("LIST_EXTEND", arg=1),
        TracedInstr("STORE_NAME", arg="attr2"),
        TracedInstr("LOAD_CONST", arg=None),
        TracedInstr("RETURN_VALUE"),
        TracedInstr("STORE_NAME", arg="Foo"),
        # ob.attr1 = 1
        TracedInstr("LOAD_CONST", arg=1),
        TracedInstr("LOAD_FAST", arg="ob"),
        TracedInstr("STORE_ATTR", arg="attr1"),
        # ob.attr2 = ob.attr2 + [ob.attr1]
        TracedInstr("LOAD_FAST", arg="ob"),
        TracedInstr("LOAD_ATTR", arg="attr2"),
        TracedInstr("LOAD_FAST", arg="ob"),
        TracedInstr("LOAD_ATTR", arg="attr1"),
        TracedInstr("BUILD_LIST", arg=1),
        add_instr,
        TracedInstr("LOAD_FAST", arg="ob"),
        TracedInstr("STORE_ATTR", arg="attr2"),
        # result = ob.attr2
        TracedInstr("LOAD_FAST", arg="ob"),
        TracedInstr("LOAD_ATTR", arg="attr2"),
        TracedInstr("STORE_FAST", arg="result"),
        # return result
        TracedInstr("LOAD_FAST", arg="result"),
        TracedInstr("RETURN_VALUE"),
    ]

    module = "tests.fixtures.slicer.attribute_dependencies"
    sliced_instructions = slice_module_at_return(module)
    assert_slice_equal(sliced_instructions, expected_instructions)


def test_data_dependency_5():
    # Explicit attribute dependencies (partial and full cover)
    if sys.version_info >= (3, 11):
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
        TracedInstr("LOAD_CONST", arg=None),
        TracedInstr("RETURN_VALUE"),
        TracedInstr("STORE_NAME", arg="Foo"),
        # ob = Foo()
        *instantiate_foo_class,
        # ob.attr1 = 1
        TracedInstr("LOAD_CONST", arg=1),
        TracedInstr("LOAD_FAST", arg="ob"),
        TracedInstr("STORE_ATTR", arg="attr1"),
        # result = ob
        TracedInstr("LOAD_FAST", arg="ob"),
        TracedInstr("STORE_FAST", arg="result"),
        # return result
        TracedInstr("LOAD_FAST", arg="result"),
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
        TracedInstr("LOAD_CONST", arg=1),
        TracedInstr("STORE_FAST", arg="foo"),
        # if foo == 1:
        TracedInstr("LOAD_FAST", arg="foo"),
        TracedInstr("LOAD_CONST", arg=1),
        TracedInstr("COMPARE_OP", arg=Compare.EQ),
        TracedInstr(
            pop_jump_if_false,
            # the first instruction of the return block
            arg=TracedInstr("LOAD_FAST", arg="result"),
        ),
        # result = 1
        TracedInstr("LOAD_CONST", arg=1),
        TracedInstr("STORE_FAST", arg="result"),
        # return result
        TracedInstr("LOAD_FAST", arg="result"),
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

    expected_instructions = [
        # result = 3
        TracedInstr("LOAD_CONST", arg=3),
        TracedInstr("STORE_FAST", arg="result"),
        # return result
        TracedInstr("LOAD_FAST", arg="result"),
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

    if sys.version_info >= (3, 11):
        jump_instruction = (
            TracedInstr(
                "JUMP_FORWARD",
                # the first instruction of the return block
                arg=TracedInstr("LOAD_FAST", arg="result"),
            ),
        )
    else:
        jump_instruction = ()

    expected_instructions = [
        # foo = 1
        TracedInstr("LOAD_CONST", arg=1),
        TracedInstr("STORE_FAST", arg="foo"),
        # bar = 2
        TracedInstr("LOAD_CONST", arg=2),
        TracedInstr("STORE_FAST", arg="bar"),
        # if foo == bar:
        TracedInstr("LOAD_FAST", arg="foo"),
        TracedInstr("LOAD_FAST", arg="bar"),
        TracedInstr("COMPARE_OP", arg=Compare.EQ),
        TracedInstr(
            pop_jump_if_false,
            # the first instruction of the elif block
            arg=TracedInstr("LOAD_FAST", arg="foo"),
        ),
        # elif foo == 1:
        TracedInstr("LOAD_FAST", arg="foo"),
        TracedInstr("LOAD_CONST", arg=1),
        TracedInstr("COMPARE_OP", arg=Compare.EQ),
        TracedInstr(
            pop_jump_if_false,
            # the first instruction of the else block
            arg=TracedInstr("LOAD_CONST", arg=3),
        ),
        # result = 2
        TracedInstr("LOAD_CONST", arg=2),
        TracedInstr("STORE_FAST", arg="result"),
        *jump_instruction,
        # return result
        TracedInstr("LOAD_FAST", arg="result"),
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

    expected_instructions = [
        # foo = 1
        TracedInstr("LOAD_CONST", arg=1),
        TracedInstr("STORE_FAST", arg="foo"),
        # bar = 2
        TracedInstr("LOAD_CONST", arg=2),
        TracedInstr("STORE_FAST", arg="bar"),
        # if foo == bar:
        TracedInstr("LOAD_FAST", arg="foo"),
        TracedInstr("LOAD_FAST", arg="bar"),
        TracedInstr("COMPARE_OP", arg=Compare.EQ),
        TracedInstr(
            pop_jump_if_false,
            # the first instruction of the elif block
            arg=TracedInstr("LOAD_FAST", arg="foo"),
        ),
        # elif foo > bar:
        TracedInstr("LOAD_FAST", arg="foo"),
        TracedInstr("LOAD_FAST", arg="bar"),
        TracedInstr("COMPARE_OP", arg=Compare.GT),
        TracedInstr(
            pop_jump_if_false,
            # the first instruction of the else block
            arg=TracedInstr("LOAD_CONST", arg=3),
        ),
        # result = 3
        TracedInstr("LOAD_CONST", arg=3),
        TracedInstr("STORE_FAST", arg="result"),
        # return result
        TracedInstr("LOAD_FAST", arg="result"),
        TracedInstr("RETURN_VALUE"),
    ]

    sliced_instructions = slice_function_at_return(func)
    assert_slice_equal(sliced_instructions, expected_instructions)
