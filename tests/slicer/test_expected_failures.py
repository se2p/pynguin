#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
# Idea and structure are taken from the pyChecco project, see:
# https://github.com/ipsw1/pychecco
# ruff: noqa: E501, ERA001
import pytest

from bytecode import BasicBlock
from bytecode import Compare
from bytecode import Instr

from tests.slicer.util import dummy_code_object
from tests.slicer.util import slice_function_at_return
from tests.slicer.util import slice_module_at_return


@pytest.mark.xfail
def test_data_dependency_composite():
    # Composite type dependencies, which are way too broad
    def func():
        # noinspection PyListCreation
        foo_list = [1, 2, 3]  # the only list operation which should be included
        foo_list.append(
            4
        )  # should not be included, and is not included (good and limitation at the same time)
        foo_list += [5]  # should not be included, but is
        foo_list[2:3] = [0, 0]  # should not be included, but is

        return foo_list[0]  # correctly included

    expected_instructions = [
        # foo_list = [1, 2, 3]
        Instr("LOAD_CONST", arg=1),
        Instr("LOAD_CONST", arg=2),
        Instr("LOAD_CONST", arg=3),
        Instr("BUILD_LIST", arg=3),
        Instr("STORE_FAST", arg="foo_list"),
        # result = foo_list[0]
        Instr("LOAD_FAST", arg="foo_list"),
        Instr("LOAD_CONST", arg=0),
        Instr("BINARY_SUBSCR"),
        Instr("STORE_FAST", arg="result"),
        # return result
        Instr("LOAD_FAST", arg="result"),
        Instr("RETURN_VALUE"),
    ]

    sliced_instructions = slice_function_at_return(func)
    assert len(sliced_instructions) == len(expected_instructions)
    # the following is not reachable
    # assert compare(sliced_instructions, expected_instructions)


@pytest.mark.xfail
def test_dunder_definition():
    def func():
        class NestedClass:
            def __init__(
                self,
            ):  # Definition of dunder methods wrongly excluded, these are not explicitly loaded
                self.x = 1

        return NestedClass()

    function_block = BasicBlock([
        # class NestedClass:
        Instr("LOAD_BUILD_CLASS"),
        Instr("LOAD_CONST", arg=dummy_code_object),
        Instr("LOAD_CONST", arg="NestedClass"),
        Instr("MAKE_FUNCTION", arg=0),
        Instr("LOAD_CONST", arg="NestedClass"),
        Instr("CALL_FUNCTION", arg=2),
        Instr("STORE_FAST", arg="NestedClass"),
        # result = NestedClass()
        Instr("LOAD_FAST", arg="NestedClass"),
        Instr("CALL_FUNCTION", arg=0),
        Instr("STORE_FAST", arg="result"),
        # return result
        Instr("LOAD_FAST", arg="result"),
        Instr("RETURN_VALUE"),
    ])

    nested_class_block = BasicBlock([
        # Definition of dunder methods are wrongly excluded, since these are not explicitly loaded
        # def __init__():
        Instr("LOAD_CONST", arg=dummy_code_object),
        Instr(
            "LOAD_CONST",
            arg="IntegrationTestLanguageFeatures.test_object_modification_call.<locals>."
            "func.<locals>.NestedClass.__init__",
        ),
        Instr("MAKE_FUNCTION", arg=0),
        Instr("STORE_NAME", arg="__init__"),
        Instr("LOAD_CONST", arg=None),
        Instr("RETURN_VALUE"),
    ])

    init_block = BasicBlock([
        # .x = 1
        Instr("LOAD_CONST", arg=1),
        Instr("LOAD_FAST", arg=""),
        Instr("STORE_ATTR", arg="x"),
        Instr("LOAD_CONST", arg=None),
        Instr("RETURN_VALUE"),
    ])

    expected_instructions = []
    expected_instructions.extend(function_block)
    expected_instructions.extend(nested_class_block)
    expected_instructions.extend(init_block)
    sliced_instructions = slice_function_at_return(func)
    assert len(sliced_instructions) == len(expected_instructions)
    # the following is not reachable
    # assert compare(sliced_instructions, expected_instructions)


@pytest.mark.xfail
def test_mod_untraced_object():
    def func():
        lst = [("foo", "3"), ("bar", "1"), ("foobar", "2")]
        lst.sort()  # This is incorrectly excluded, since it is not known that the method modifies the list

        return lst

    function_block = BasicBlock([
        # lst = [('foo', '3'), ('bar', '1'), ('foobar', '2')]
        Instr("LOAD_CONST", arg=("foo", "3")),
        Instr("LOAD_CONST", arg=("bar", "1")),
        Instr("LOAD_CONST", arg=("foobar", "2")),
        Instr("BUILD_LIST", arg=3),
        Instr("STORE_FAST", arg="lst"),
        # lst.sort()
        # This is incorrectly excluded, since it is not known that the method modifies the list
        Instr("LOAD_FAST", arg="lst"),
        Instr("LOAD_METHOD", arg="sort"),
        Instr("CALL_METHOD", arg=0),
        Instr("POP_TOP"),
        # result = lst
        Instr("LOAD_FAST", arg="lst"),
        Instr("STORE_FAST", arg="result"),
        # return result
        Instr("LOAD_FAST", arg="result"),
        Instr("RETURN_VALUE"),
    ])

    expected_instructions = []
    expected_instructions.extend(function_block)
    sliced_instructions = slice_function_at_return(func)
    assert len(sliced_instructions) == len(expected_instructions)
    # the following is not reachable
    # assert compare(sliced_instructions, expected_instructions)


@pytest.mark.xfail
def test_call_unused_argument():
    # Call with two arguments, one of which is used in the callee

    module_block = BasicBlock([
        # def callee():
        Instr("LOAD_NAME", arg="int"),
        Instr("LOAD_NAME", arg="int"),
        Instr("LOAD_CONST", arg=("a", "b")),
        Instr("BUILD_CONST_KEY_MAP", arg=2),
        Instr("LOAD_CONST", arg=dummy_code_object),
        Instr("LOAD_CONST", arg="callee"),
        Instr("MAKE_FUNCTION", arg=4),
        Instr("STORE_NAME", arg="callee"),
        # foo = 1
        Instr("LOAD_CONST", arg=1),
        Instr("STORE_NAME", arg="foo"),
        # bar = 2
        # This argument is not used by the callee and should therefore be excluded.
        # But it is an implicit data dependency of the call and is incorrectly and imprecisely included.
        # Instr("LOAD_CONST", arg=2),
        # Instr("STORE_NAME", arg="bar"),
        # result = callee()
        Instr("LOAD_NAME", arg="callee"),
        Instr("LOAD_NAME", arg="foo"),
        # Instr("LOAD_NAME", arg="bar"),
        Instr("CALL_FUNCTION", arg=2),
        Instr("STORE_NAME", arg="result"),
        # return result
        Instr("LOAD_CONST", arg=None),
        Instr("RETURN_VALUE"),
    ])
    callee_block = BasicBlock([
        # return a
        Instr("LOAD_FAST", arg="a"),
        Instr("RETURN_VALUE"),
    ])

    expected_instructions = []
    expected_instructions.extend(module_block)
    expected_instructions.extend(callee_block)

    module = "tests.fixtures.slicer.simple_call_arg"
    sliced_instructions = slice_module_at_return(module)
    assert len(sliced_instructions) == len(expected_instructions)
    # the following is not reachable
    # assert compare(sliced_instructions, expected_instructions)


@pytest.mark.xfail
def test_exception():
    # Exception
    def func():
        foo = 1
        bar = 0

        try:
            result = 0 / 0
        except ZeroDivisionError:
            result = foo + bar

        return result

    assert func() == 1

    dummy_block = BasicBlock([])

    return_block = BasicBlock([
        # return result
        Instr("LOAD_FAST", arg="result"),
        Instr("RETURN_VALUE"),
    ])
    try_block = BasicBlock([
        # result = foo / bar <- did somehow effect slicing criterion...
        Instr("LOAD_FAST", arg="foo"),
        Instr("LOAD_FAST", arg="bar"),
        Instr("BINARY_TRUE_DIVIDE"),
        # except ZeroDivisionError:
        Instr("DUP_TOP"),
        Instr("LOAD_GLOBAL", arg="ZeroDivisionError"),
        Instr("COMPARE_OP", arg=Compare.EXC_MATCH),
        Instr("POP_JUMP_IF_FALSE", arg=dummy_block),
    ])
    except_block = BasicBlock([
        # result = foo + bar
        Instr("LOAD_FAST", arg="foo"),
        Instr("LOAD_FAST", arg="bar"),
        Instr("BINARY_ADD"),
        Instr("STORE_FAST", arg="result"),
        Instr("JUMP_FORWARD", arg=dummy_block),
    ])
    function_block = BasicBlock([
        # foo = 1
        Instr("LOAD_CONST", arg=1),  # <- excluded because no stack simulation
        Instr("STORE_FAST", arg="foo"),
        # bar = 0
        Instr("LOAD_CONST", arg=0),  # <- excluded because no stack simulation
        Instr("STORE_FAST", arg="bar"),
        # try:
        # Instr("SETUP_FINALLY", arg=try_block),
    ])

    expected_instructions = []
    expected_instructions.extend(return_block)
    expected_instructions.extend(except_block)
    expected_instructions.extend(function_block)
    expected_instructions.extend(try_block)

    sliced_instructions = slice_function_at_return(func)
    assert len(sliced_instructions) == len(expected_instructions)
    # the following is not reachable
    # assert compare(sliced_instructions, expected_instructions)


@pytest.mark.xfail
def test_data_dependency_6():
    def func() -> int:
        class Plus:
            calculations = 0  # falsely included

            def plus_four(self, number):
                self.calculations += 1  # falsely included
                return number + 4

        plus_0 = Plus()
        int_0 = 42
        var_1 = plus_0.plus_four(int_0)
        return plus_0.plus_four(var_1)

    sliced_instructions = slice_function_at_return(func)
    checked_lines = set()
    checked_lines.update(instr.lineno for instr in sliced_instructions)
    expected_lines = {293, 296, 298, 300, 301, 302, 303, 304}

    # same as expected_lines == checked_lines, but with nicer output on failure
    assert checked_lines.difference(expected_lines) == {}
