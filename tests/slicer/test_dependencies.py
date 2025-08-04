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

from bytecode.cfg import BasicBlock
from bytecode.instr import BinaryOp
from bytecode.instr import Compare
from bytecode.instr import Instr

from tests.slicer.util import compare
from tests.slicer.util import dummy_code_object
from tests.slicer.util import slice_function_at_return
from tests.slicer.util import slice_module_at_return


if sys.version_info >= (3, 11):
    add_instr = Instr("BINARY_OP", arg=BinaryOp.ADD.value)
    create_foo_class = (
        Instr("PUSH_NULL"),
        Instr("LOAD_BUILD_CLASS"),
        Instr("LOAD_CONST", arg=dummy_code_object),
        Instr("MAKE_FUNCTION", arg=0),
        Instr("LOAD_CONST", arg="Foo"),
        Instr("PRECALL", arg=2),
        Instr("CALL", arg=2),
        Instr("STORE_NAME", arg="Foo"),
    )
    pop_jump_if_false = "POP_JUMP_FORWARD_IF_FALSE"
else:
    add_instr = Instr("BINARY_ADD")
    create_foo_class = (
        Instr("LOAD_BUILD_CLASS"),
        Instr("LOAD_CONST", arg=dummy_code_object),
        Instr("LOAD_CONST", arg="Foo"),
        Instr("MAKE_FUNCTION", arg=0),
        Instr("LOAD_CONST", arg="Foo"),
        Instr("CALL_FUNCTION", arg=2),
        Instr("STORE_NAME", arg="Foo"),
    )
    pop_jump_if_false = "POP_JUMP_IF_FALSE"


def test_data_dependency_1():
    # Implicit data dependency at return, explicit (full cover) for result
    def func() -> int:
        result = 1
        return result  # noqa: RET504

    expected_instructions = [
        # result = 1
        Instr("LOAD_CONST", arg=1),
        Instr("STORE_FAST", arg="result"),
        # return result
        Instr("LOAD_FAST", arg="result"),
        Instr("RETURN_VALUE"),
    ]

    sliced_instructions = slice_function_at_return(func)
    assert len(sliced_instructions) == len(expected_instructions)
    assert compare(sliced_instructions, expected_instructions)


def test_data_dependency_2():
    # Implicit data dependency at return, explicit (full cover) for result;
    # foo must be excluded
    def func() -> int:
        result = 1
        foo = 2  # noqa: F841
        return result

    expected_instructions = [
        # result = 1
        Instr("LOAD_CONST", arg=1),
        Instr("STORE_FAST", arg="result"),
        # return result
        Instr("LOAD_FAST", arg="result"),
        Instr("RETURN_VALUE"),
    ]

    sliced_instructions = slice_function_at_return(func)
    assert len(sliced_instructions) == len(expected_instructions)
    assert compare(sliced_instructions, expected_instructions)


def test_data_dependency_3():
    # Transitive explicit (full cover) dependencies
    def func() -> int:
        foo = 1
        result = 1 + foo
        return result  # noqa: RET504

    expected_instructions = [
        # foo = 1
        Instr("LOAD_CONST", arg=1),
        Instr("STORE_FAST", arg="foo"),
        # result = 1 + foo
        Instr("LOAD_CONST", arg=1),
        Instr("LOAD_FAST", arg="foo"),
        add_instr,
        Instr("STORE_FAST", arg="result"),
        # return result
        Instr("LOAD_FAST", arg="result"),
        Instr("RETURN_VALUE"),
    ]

    sliced_instructions = slice_function_at_return(func)
    assert len(sliced_instructions) == len(expected_instructions)
    assert compare(sliced_instructions, expected_instructions)


def test_data_dependency_4():
    # Explicit attribute dependencies (full cover)
    module_block = BasicBlock([
        # class Foo:
        *create_foo_class,
        # ob.attr1 = 1
        Instr("LOAD_CONST", arg=1),
        Instr("LOAD_FAST", arg="ob"),
        Instr("STORE_ATTR", arg="attr1"),
        # ob.attr2 = ob.attr2 + [ob.attr1]
        Instr("LOAD_FAST", arg="ob"),
        Instr("LOAD_ATTR", arg="attr2"),
        Instr("LOAD_FAST", arg="ob"),
        Instr("LOAD_ATTR", arg="attr1"),
        Instr("BUILD_LIST", arg=1),
        add_instr,
        Instr("LOAD_FAST", arg="ob"),
        Instr("STORE_ATTR", arg="attr2"),
        # result = ob.attr2
        Instr("LOAD_FAST", arg="ob"),
        Instr("LOAD_ATTR", arg="attr2"),
        Instr("STORE_FAST", arg="result"),
        # return
        Instr("LOAD_FAST", arg="result"),
        Instr("RETURN_VALUE"),
    ])
    class_attr_block = BasicBlock([
        # attr2 = [1, 2, 3]
        Instr("BUILD_LIST", arg=0),
        Instr("LOAD_CONST", arg=(1, 2, 3)),
        Instr("LIST_EXTEND", arg=1),
        Instr("STORE_NAME", arg="attr2"),
        # return
        Instr("LOAD_CONST", arg=None),
        Instr("RETURN_VALUE"),
    ])

    expected_instructions = []
    expected_instructions.extend(module_block)
    expected_instructions.extend(class_attr_block)

    module = "tests.fixtures.slicer.attribute_dependencies"
    sliced_instructions = slice_module_at_return(module)
    assert len(sliced_instructions) == len(expected_instructions)
    assert compare(sliced_instructions, expected_instructions)


def test_data_dependency_5():
    if sys.version_info >= (3, 11):
        instantiate_foo_class = (
            Instr("LOAD_GLOBAL", arg=(True, "Foo")),
            Instr("STORE_FAST", arg="ob"),
            Instr("PRECALL", arg=0),
            Instr("CALL", arg=0),
        )
    else:
        instantiate_foo_class = (
            Instr("LOAD_GLOBAL", arg="Foo"),
            Instr("CALL_FUNCTION", arg=0),
            Instr("STORE_FAST", arg="ob"),
        )
    # Explicit attribute dependencies (partial and full cover)
    module_block = BasicBlock([
        # class Foo:
        *create_foo_class,
        # ob = Foo()
        *instantiate_foo_class,
        # ob.attr1 = 1
        Instr("LOAD_CONST", arg=1),
        Instr("LOAD_FAST", arg="ob"),
        Instr("STORE_ATTR", arg="attr1"),
        # result = ob
        Instr("LOAD_FAST", arg="ob"),
        Instr("STORE_FAST", arg="result"),
        # return
        Instr("LOAD_FAST", arg="result"),
        Instr("RETURN_VALUE"),
    ])
    class_attr_block = BasicBlock([
        Instr("LOAD_CONST", arg=None),
        Instr("RETURN_VALUE"),
    ])

    expected_instructions = []
    expected_instructions.extend(module_block)
    expected_instructions.extend(class_attr_block)

    module = "tests.fixtures.slicer.partial_cover_dependency"
    sliced_instructions = slice_module_at_return(module)
    assert len(sliced_instructions) == len(expected_instructions)
    assert compare(sliced_instructions, expected_instructions)


def test_simple_control_dependency_1():
    # If condition evaluated to true, with relevant variable foo
    def func() -> int:  # pragma: no cover
        foo = 1
        result = 3

        if foo == 1:
            result = 1

        return result

    return_basic_block = BasicBlock([
        # return result
        Instr("LOAD_FAST", arg="result"),
        Instr("RETURN_VALUE"),
    ])
    if_basic_block = BasicBlock([
        # result = 1
        Instr("LOAD_CONST", arg=1),
        Instr("STORE_FAST", arg="result"),
    ])
    init_basic_block = BasicBlock([
        # foo = 1
        Instr("LOAD_CONST", arg=1),
        Instr("STORE_FAST", arg="foo"),
        # if foo == 1
        Instr("LOAD_FAST", arg="foo"),
        Instr("LOAD_CONST", arg=1),
        Instr("COMPARE_OP", arg=Compare.EQ),
        Instr(pop_jump_if_false, arg=return_basic_block),
    ])

    expected_instructions = []
    expected_instructions.extend(init_basic_block)
    expected_instructions.extend(if_basic_block)
    expected_instructions.extend(return_basic_block)

    sliced_instructions = slice_function_at_return(func)
    assert len(sliced_instructions) == len(expected_instructions)
    assert compare(sliced_instructions, expected_instructions)


def test_simple_control_dependency_2():
    # If condition evaluated to false, with two relevant variables (but no influence on result)
    def func() -> int:  # pragma: no cover
        foo = 1
        bar = 2
        result = 3

        if foo == bar:
            result = 1

        return result

    init_basic_block = BasicBlock([
        # result = 3
        Instr("LOAD_CONST", arg=3),
        Instr("STORE_FAST", arg="result"),
    ])
    return_basic_block = BasicBlock([
        # return result
        Instr("LOAD_FAST", arg="result"),
        Instr("RETURN_VALUE"),
    ])

    expected_instructions = []
    expected_instructions.extend(init_basic_block)
    expected_instructions.extend(return_basic_block)

    sliced_instructions = slice_function_at_return(func)
    assert len(sliced_instructions) == len(expected_instructions)
    assert compare(sliced_instructions, expected_instructions)


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

    # result = 2
    if sys.version_info >= (3, 11):
        return_block = BasicBlock([
            Instr("LOAD_FAST", arg="result"),
            Instr("RETURN_VALUE"),
        ])
        elif_body = BasicBlock([
            Instr("LOAD_CONST", arg=2),
            Instr("STORE_FAST", arg="result"),
            Instr("JUMP_FORWARD", arg=return_block),
        ])
    else:
        elif_body = BasicBlock([
            Instr("LOAD_CONST", arg=2),
            Instr("STORE_FAST", arg="result"),
            Instr("LOAD_FAST", arg="result"),
            Instr("RETURN_VALUE"),
        ])
        return_block = BasicBlock([])

    else_block = BasicBlock([
        Instr("LOAD_CONST", arg=3),
        Instr("STORE_FAST", arg="result"),
    ])
    elif_cond = BasicBlock([
        # elif foo == 1:
        Instr("LOAD_FAST", arg="foo"),
        Instr("LOAD_CONST", arg=1),
        Instr("COMPARE_OP", arg=Compare.EQ),
        Instr(pop_jump_if_false, arg=else_block),
    ])
    if_cond = BasicBlock([
        # if foo == bar
        Instr("LOAD_FAST", arg="foo"),
        Instr("LOAD_FAST", arg="bar"),
        Instr("COMPARE_OP", arg=Compare.EQ),
        Instr(pop_jump_if_false, arg=elif_cond),
    ])
    init_block = BasicBlock([
        # foo = 1
        Instr("LOAD_CONST", arg=1),
        Instr("STORE_FAST", arg="foo"),
        # bar = 2
        Instr("LOAD_CONST", arg=2),
        Instr("STORE_FAST", arg="bar"),
    ])

    expected_instructions = []
    expected_instructions.extend(init_block)
    expected_instructions.extend(if_cond)
    expected_instructions.extend(elif_cond)
    expected_instructions.extend(elif_body)
    expected_instructions.extend(return_block)

    sliced_instructions = slice_function_at_return(func)
    assert len(sliced_instructions) == len(expected_instructions)
    assert compare(sliced_instructions, expected_instructions)


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

    return_block = BasicBlock([
        # return result
        Instr("LOAD_FAST", arg="result"),
        Instr("RETURN_VALUE"),
    ])
    else_block = BasicBlock([
        # result = 3
        Instr("LOAD_CONST", arg=3),
        Instr("STORE_FAST", arg="result"),
    ])
    elif_cond = BasicBlock([
        # elif foo == 1:
        Instr("LOAD_FAST", arg="foo"),
        Instr("LOAD_FAST", arg="bar"),
        Instr("COMPARE_OP", arg=Compare.GT),
        Instr(pop_jump_if_false, arg=else_block),
    ])
    if_cond = BasicBlock([
        # if foo == bar
        Instr("LOAD_FAST", arg="foo"),
        Instr("LOAD_FAST", arg="bar"),
        Instr("COMPARE_OP", arg=Compare.EQ),
        Instr(pop_jump_if_false, arg=elif_cond),
    ])
    init_block = BasicBlock([
        # foo = 1
        Instr("LOAD_CONST", arg=1),
        Instr("STORE_FAST", arg="foo"),
        # bar = 2
        Instr("LOAD_CONST", arg=2),
        Instr("STORE_FAST", arg="bar"),
    ])

    expected_instructions = []
    expected_instructions.extend(init_block)
    expected_instructions.extend(if_cond)
    expected_instructions.extend(elif_cond)
    expected_instructions.extend(else_block)
    expected_instructions.extend(return_block)

    sliced_instructions = slice_function_at_return(func)
    assert len(sliced_instructions) == len(expected_instructions)
    assert compare(sliced_instructions, expected_instructions)
