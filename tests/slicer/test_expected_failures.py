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
from bytecode.instr import TryEnd

from tests.slicer.util import TracedInstr
from tests.slicer.util import assert_slice_equal
from tests.slicer.util import dummy_code_object
from tests.slicer.util import slice_function_at_return
from tests.slicer.util import slice_function_at_return_with_result
from tests.slicer.util import slice_module_at_return

if sys.version_info >= (3, 14):
    inplace_add_instruction = TracedInstr("BINARY_OP", arg=BinaryOp.INPLACE_ADD.value)
    binary_add_instruction = TracedInstr("BINARY_OP", arg=BinaryOp.ADD.value)
    store_slice = (TracedInstr("STORE_SLICE"),)
    load_const = "LOAD_SMALL_INT"
    load_fast = "LOAD_FAST_BORROW"
    binary_subscr = (TracedInstr("BINARY_OP", arg=BinaryOp.SUBSCR.value),)
    load_slice = lambda arg1, arg2: (
        TracedInstr("LOAD_CONST", arg=slice(arg1, arg2)),
        TracedInstr("STORE_SUBSCR"),
    )
elif sys.version_info >= (3, 12):
    inplace_add_instruction = TracedInstr("BINARY_OP", arg=BinaryOp.INPLACE_ADD.value)
    binary_add_instruction = TracedInstr("BINARY_OP", arg=BinaryOp.ADD.value)
    store_slice = (TracedInstr("STORE_SLICE"),)
    load_const = "LOAD_SMALL"
    load_fast = "LOAD_FAST"
    binary_subscr = (TracedInstr("BINARY_SUBSCR"),)
    load_slice = lambda arg1, arg2: (
        TracedInstr("LOAD_CONST", arg=arg1),
        TracedInstr("LOAD_CONST", arg=arg2),
        TracedInstr(name='STORE_SLICE', arg=0)
    )
elif sys.version_info >= (3, 11):
    inplace_add_instruction = TracedInstr("BINARY_OP", arg=BinaryOp.INPLACE_ADD.value)
    binary_add_instruction = TracedInstr("BINARY_OP", arg=BinaryOp.ADD.value)
    store_slice = (
        TracedInstr("BUILD_SLICE", arg=2),
        TracedInstr("STORE_SUBSCR"),
    )
    binary_subscr = (TracedInstr("BINARY_SUBSCR"),)
    load_const = "LOAD_SMALL"
    load_fast = "LOAD_FAST"
    load_slice = lambda arg1, arg2: (
        TracedInstr("LOAD_CONST", arg=arg1),
        TracedInstr("LOAD_CONST", arg=arg2),
        TracedInstr(name='STORE_SLICE', arg=0)
    )
else:
    inplace_add_instruction = TracedInstr("INPLACE_ADD")
    binary_add_instruction = TracedInstr("BINARY_ADD")
    store_slice = (
        TracedInstr("BUILD_SLICE", arg=2),
        TracedInstr("STORE_SUBSCR"),
    )
    binary_subscr = (TracedInstr("BINARY_SUBSCR"),)
    load_const = "LOAD_SMALL"
    load_fast = "LOAD_FAST"
    load_slice = lambda arg1, arg2: (
        TracedInstr("LOAD_CONST", arg=arg1),
        TracedInstr("LOAD_CONST", arg=arg2),
        TracedInstr(name='STORE_SLICE', arg=0)
    )


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
        TracedInstr("BUILD_LIST", arg=0),
        TracedInstr("LOAD_CONST", arg=(1, 2, 3)),
        TracedInstr("LIST_EXTEND", arg=1),
        TracedInstr("STORE_FAST", arg="foo_list"),
        # BAD: foo_list += [5]
        TracedInstr(load_fast, arg="foo_list"),
        TracedInstr(load_const, arg=5),
        TracedInstr("BUILD_LIST", arg=1),
        inplace_add_instruction,
        TracedInstr("STORE_FAST", arg="foo_list"),
        # BAD: foo_list[2:3] = [0, 0]
        TracedInstr(load_const, arg=0),
        TracedInstr(load_const, arg=0),
        TracedInstr("BUILD_LIST", arg=2),
        TracedInstr(load_fast, arg="foo_list"),
        *load_slice(2, 3),
        # return foo_list[0]
        TracedInstr(load_fast, arg="foo_list"),
        TracedInstr(load_const, arg=0),
        *binary_subscr,
        TracedInstr("RETURN_VALUE"),
    ]

    sliced_instructions = slice_function_at_return(func)
    assert_slice_equal(sliced_instructions, expected_instructions)


def test_dunder_definition():
    def func():
        class NestedClass:
            def __init__(
                self,
            ):  # Definition of dunder methods wrongly excluded as they are not explicitly loaded
                self.x = 1

        return NestedClass()

    if sys.version_info >= (3, 14):
        create_nested_class = (
            TracedInstr("LOAD_BUILD_CLASS"),
            TracedInstr("PUSH_NULL"),
            TracedInstr("LOAD_CONST", arg=dummy_code_object),
            TracedInstr("MAKE_FUNCTION"),
            TracedInstr("LOAD_CONST", arg="NestedClass"),
            TracedInstr("CALL", arg=2),
            TracedInstr("LOAD_CONST", arg=None),
            TracedInstr("RETURN_VALUE"),
        )
        call_nested_class = (
            TracedInstr(load_fast, arg="NestedClass"),
            TracedInstr("PUSH_NULL"),
            TracedInstr("CALL", arg=0),
            # MISSING: __init__ method call
            TracedInstr("LOAD_CONST", arg=None),
            TracedInstr("RETURN_VALUE"),
        )
    elif sys.version_info >= (3, 13):
        create_nested_class = (
            TracedInstr("LOAD_BUILD_CLASS"),
            TracedInstr("PUSH_NULL"),
            TracedInstr("LOAD_CONST", arg=dummy_code_object),
            TracedInstr("MAKE_FUNCTION"),
            TracedInstr("LOAD_CONST", arg="NestedClass"),
            TracedInstr("CALL", arg=2),
            TracedInstr("RETURN_CONST", arg=None),
        )
        call_nested_class = (
            TracedInstr("LOAD_FAST", arg="NestedClass"),
            TracedInstr("PUSH_NULL"),
            TracedInstr("CALL", arg=0),
            # MISSING: __init__ method call
            TracedInstr("RETURN_CONST", arg=None),
        )
    elif sys.version_info >= (3, 12):
        create_nested_class = (
            TracedInstr("PUSH_NULL"),
            TracedInstr("LOAD_BUILD_CLASS"),
            TracedInstr("LOAD_CONST", arg=dummy_code_object),
            TracedInstr("MAKE_FUNCTION", arg=0),
            TracedInstr("LOAD_CONST", arg="NestedClass"),
            TracedInstr("CALL", arg=2),
            TracedInstr("RETURN_CONST", arg=None),
        )
        call_nested_class = (
            TracedInstr("PUSH_NULL"),
            TracedInstr("LOAD_FAST", arg="NestedClass"),
            TracedInstr("CALL", arg=0),
            # MISSING: __init__ method call
            TracedInstr("RETURN_CONST", arg=None),
        )
    elif sys.version_info >= (3, 11):
        create_nested_class = (
            TracedInstr("PUSH_NULL"),
            TracedInstr("LOAD_BUILD_CLASS"),
            TracedInstr("LOAD_CONST", arg=dummy_code_object),
            TracedInstr("MAKE_FUNCTION", arg=0),
            TracedInstr("LOAD_CONST", arg="NestedClass"),
            TracedInstr("PRECALL", arg=2),
            TracedInstr("CALL", arg=2),
            TracedInstr("LOAD_CONST", arg=None),
            TracedInstr("RETURN_VALUE"),
        )
        call_nested_class = (
            TracedInstr("PUSH_NULL"),
            TracedInstr("LOAD_FAST", arg="NestedClass"),
            TracedInstr("PRECALL", arg=0),
            TracedInstr("CALL", arg=0),
            # MISSING: __init__ method call
            TracedInstr("LOAD_CONST", arg=None),
            TracedInstr("RETURN_VALUE"),
        )
    else:
        create_nested_class = (
            TracedInstr("LOAD_BUILD_CLASS"),
            TracedInstr("LOAD_CONST", arg=dummy_code_object),
            TracedInstr("LOAD_CONST", arg="NestedClass"),
            TracedInstr("MAKE_FUNCTION", arg=0),
            TracedInstr("LOAD_CONST", arg="NestedClass"),
            TracedInstr("CALL_FUNCTION", arg=2),
            TracedInstr("LOAD_CONST", arg=None),
            TracedInstr("RETURN_VALUE"),
        )
        call_nested_class = (
            TracedInstr("LOAD_FAST", arg="NestedClass"),
            TracedInstr("CALL_FUNCTION", arg=0),
            # MISSING: __init__ method call
            TracedInstr("LOAD_CONST", arg=None),
            TracedInstr("RETURN_VALUE"),
        )

    expected_instructions = [
        # class NestedClass:
        *create_nested_class,
        TracedInstr("STORE_FAST", arg="NestedClass"),
        # return NestedClass()
        *call_nested_class,
        TracedInstr("RETURN_VALUE"),
    ]

    sliced_instructions = slice_function_at_return(func)
    assert_slice_equal(sliced_instructions, expected_instructions)


def test_mod_untraced_object():
    def func():
        lst = [("foo", "3"), ("bar", "1"), ("foobar", "2")]
        lst.sort()  # This is incorrectly excluded, since it is not known that the method modifies the list

        return lst

    expected_instructions = [
        # lst = [('foo', '3'), ('bar', '1'), ('foobar', '2')]
        TracedInstr("BUILD_LIST", arg=0),
        TracedInstr(load_const, arg=(("foo", "3"), ("bar", "1"), ("foobar", "2"))),
        TracedInstr("LIST_EXTEND", arg=1),
        TracedInstr("STORE_FAST", arg="lst"),
        # MISSING: lst.sort()
        # return lst
        TracedInstr(load_fast, arg="lst"),
        TracedInstr("RETURN_VALUE"),
    ]

    sliced_instructions = slice_function_at_return(func)
    assert_slice_equal(sliced_instructions, expected_instructions)


def test_call_unused_argument():
    # Call with two arguments, one of which is used in the callee
    if sys.version_info >= (3, 13):
        create_callee = (
            TracedInstr(load_const, arg="a"),
            TracedInstr("LOAD_NAME", arg="int"),
            TracedInstr(load_const, arg="b"),
            TracedInstr("LOAD_NAME", arg="int"),
            TracedInstr("BUILD_TUPLE", arg=4),
            TracedInstr(load_const, arg=dummy_code_object),
            TracedInstr("MAKE_FUNCTION"),
            TracedInstr("SET_FUNCTION_ATTRIBUTE", arg=4),
        )
        call_callee = (
            TracedInstr("LOAD_GLOBAL", arg=(True, "callee")),
            TracedInstr("LOAD_FAST_LOAD_FAST", arg=("foo", "bar")),
            TracedInstr("CALL", arg=2),
            TracedInstr(load_fast, arg="a"),
            TracedInstr("RETURN_VALUE"),
        )
    elif sys.version_info >= (3, 12):
        create_callee = (
            TracedInstr("LOAD_CONST", arg="a"),
            TracedInstr("LOAD_NAME", arg="int"),
            TracedInstr("LOAD_CONST", arg="b"),
            TracedInstr("LOAD_NAME", arg="int"),
            TracedInstr("BUILD_TUPLE", arg=4),
            TracedInstr("LOAD_CONST", arg=dummy_code_object),
            TracedInstr("MAKE_FUNCTION", arg=4),
        )
        call_callee = (
            TracedInstr("LOAD_GLOBAL", arg=(True, "callee")),
            TracedInstr("LOAD_FAST", arg="foo"),
            TracedInstr("LOAD_FAST", arg="bar"),
            TracedInstr("CALL", arg=2),
            TracedInstr("LOAD_FAST", arg="a"),
            TracedInstr("RETURN_VALUE"),
        )
    elif sys.version_info >= (3, 11):
        create_callee = (
            TracedInstr("LOAD_CONST", arg="a"),
            TracedInstr("LOAD_NAME", arg="int"),
            TracedInstr("LOAD_CONST", arg="b"),
            TracedInstr("LOAD_NAME", arg="int"),
            TracedInstr("BUILD_TUPLE", arg=4),
            TracedInstr("LOAD_CONST", arg=dummy_code_object),
            TracedInstr("MAKE_FUNCTION", arg=4),
        )
        call_callee = (
            TracedInstr("LOAD_GLOBAL", arg=(True, "callee")),
            TracedInstr("LOAD_FAST", arg="foo"),
            TracedInstr("LOAD_FAST", arg="bar"),
            TracedInstr("PRECALL", arg=2),
            TracedInstr("CALL", arg=2),
            TracedInstr("LOAD_FAST", arg="a"),
            TracedInstr("RETURN_VALUE"),
        )
    else:
        create_callee = (
            TracedInstr("LOAD_CONST", arg="a"),
            TracedInstr("LOAD_NAME", arg="int"),
            TracedInstr("LOAD_CONST", arg="b"),
            TracedInstr("LOAD_NAME", arg="int"),
            TracedInstr("BUILD_TUPLE", arg=4),
            TracedInstr("LOAD_CONST", arg=dummy_code_object),
            TracedInstr("LOAD_CONST", arg="callee"),
            TracedInstr("MAKE_FUNCTION", arg=4),
        )
        call_callee = (
            TracedInstr("LOAD_GLOBAL", arg="callee"),
            TracedInstr("LOAD_FAST", arg="foo"),
            TracedInstr("LOAD_FAST", arg="bar"),
            TracedInstr("CALL_FUNCTION", arg=2),
            TracedInstr("LOAD_FAST", arg="a"),
            TracedInstr("RETURN_VALUE"),
        )

    expected_instructions = [
        # def callee(a: int, b: int):
        *create_callee,
        TracedInstr("STORE_NAME", arg="callee"),
        # foo = 1
        TracedInstr(load_const, arg=1),
        TracedInstr("STORE_FAST", arg="foo"),
        # BAD: bar = 2
        # This argument is not used by the callee and should therefore be excluded.
        # But it is an implicit data dependency of the call and is incorrectly and imprecisely included.
        # result = callee()
        TracedInstr(load_const, arg=2),
        TracedInstr("STORE_FAST", arg="bar"),
        # result = callee(foo, bar)
        *call_callee,
        TracedInstr("STORE_FAST", arg="result"),
        # return result
        TracedInstr(load_fast, arg="result"),
        TracedInstr("RETURN_VALUE"),
    ]

    module = "tests.fixtures.slicer.simple_call_arg"
    sliced_instructions = slice_module_at_return(module)
    assert_slice_equal(sliced_instructions, expected_instructions)


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

    if sys.version_info >= (3, 13):
        catch_exception = (
            TracedInstr("LOAD_GLOBAL", arg=(False, "ZeroDivisionError")),
            TracedInstr("CHECK_EXC_MATCH"),
            TracedInstr("POP_JUMP_IF_FALSE", arg=TryEnd(0)),
        )
        jump_instruction = ()
        load_foo_and_bar = (TracedInstr("LOAD_FAST_LOAD_FAST", arg=("foo", "bar")),)
    elif sys.version_info >= (3, 12):
        catch_exception = (
            TracedInstr("LOAD_GLOBAL", arg=(False, "ZeroDivisionError")),
            TracedInstr("CHECK_EXC_MATCH"),
            TracedInstr("POP_JUMP_IF_FALSE", arg=TryEnd(0)),
        )
        jump_instruction = ()
        load_foo_and_bar = (
            TracedInstr("LOAD_FAST", arg="foo"),
            TracedInstr("LOAD_FAST", arg="bar"),
        )
    elif sys.version_info >= (3, 11):
        catch_exception = (
            TracedInstr("LOAD_GLOBAL", arg=(False, "ZeroDivisionError")),
            TracedInstr("CHECK_EXC_MATCH"),
            TracedInstr("POP_JUMP_FORWARD_IF_FALSE", arg=TryEnd(0)),
        )
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
        catch_exception = (
            TracedInstr("DUP_TOP"),
            TracedInstr("LOAD_GLOBAL", arg="ZeroDivisionError"),
            TracedInstr(
                "JUMP_IF_NOT_EXC_MATCH",
                # the first instruction of the exception not catched block
                arg=TracedInstr("RERAISE", arg=0),
            ),
        )
        jump_instruction = ()
        load_foo_and_bar = (
            TracedInstr("LOAD_FAST", arg="foo"),
            TracedInstr("LOAD_FAST", arg="bar"),
        )

    expected_instructions = [
        # foo = 1
        TracedInstr("STORE_FAST", arg="foo"),
        # MISSING: 1
        # bar = 0
        TracedInstr("STORE_FAST", arg="bar"),
        # MISSING: 0
        # except ZeroDivisionError:
        *catch_exception,
        # result = foo + bar
        *load_foo_and_bar,
        binary_add_instruction,
        TracedInstr("STORE_FAST", arg="result"),
        *jump_instruction,
        # return result
        TracedInstr(load_fast, arg="result"),
        TracedInstr("RETURN_VALUE"),
    ]

    sliced_instructions, result = slice_function_at_return_with_result(func)
    assert result == 1
    assert_slice_equal(sliced_instructions, expected_instructions)


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

    if sys.version_info >= (3, 13):
        create_plus = (
            TracedInstr("LOAD_BUILD_CLASS"),
            TracedInstr("PUSH_NULL"),
            TracedInstr(load_const, arg=dummy_code_object),
            TracedInstr("MAKE_FUNCTION"),
            TracedInstr(load_const, arg="Plus"),
            TracedInstr("CALL", arg=2),
            # BAD: falsely included
            TracedInstr(load_const, arg=0),
            TracedInstr("STORE_NAME", arg="calculations"),
            TracedInstr(load_const, arg=dummy_code_object),
            TracedInstr("MAKE_FUNCTION"),
            TracedInstr("STORE_NAME", arg="plus_four"),
            TracedInstr("RETURN_CONST", arg=None),
        )
        call_plus = (
            TracedInstr(load_fast, arg="Plus"),
            TracedInstr("PUSH_NULL"),
            TracedInstr("CALL", arg=0),
        )
        call_plus_four_int = (
            TracedInstr(load_fast, arg="plus_0"),
            TracedInstr("LOAD_ATTR", arg=(True, "plus_four")),
            TracedInstr(load_fast, arg="int_0"),
            TracedInstr("CALL", arg=1),
            # BAD: self.calculations += 1
            TracedInstr(load_fast, arg="self"),
            TracedInstr("COPY", arg=1),
            TracedInstr("LOAD_ATTR", arg=(False, "calculations")),
            TracedInstr(load_const, arg=1),
            TracedInstr("BINARY_OP", arg=BinaryOp.INPLACE_ADD.value),
            TracedInstr("SWAP", arg=2),
            TracedInstr("STORE_ATTR", arg="calculations"),
            # return number + 4
            TracedInstr(load_fast, arg="number"),
            TracedInstr(load_const, arg=4),
            TracedInstr("BINARY_OP", arg=0),
            TracedInstr("RETURN_VALUE"),
        )
        call_plus_four_var = (
            TracedInstr(load_fast, arg="plus_0"),
            TracedInstr("LOAD_ATTR", arg=(True, "plus_four")),
            TracedInstr(load_fast, arg="var_1"),
            TracedInstr("CALL", arg=1),
        )
    elif sys.version_info >= (3, 12):
        create_plus = (
            TracedInstr("PUSH_NULL"),
            TracedInstr("LOAD_BUILD_CLASS"),
            TracedInstr("LOAD_CONST", arg=dummy_code_object),
            TracedInstr("MAKE_FUNCTION", arg=0),
            TracedInstr("LOAD_CONST", arg="Plus"),
            TracedInstr("CALL", arg=2),
            # BAD: falsely included
            TracedInstr("LOAD_CONST", arg=0),
            TracedInstr("STORE_NAME", arg="calculations"),
            TracedInstr("LOAD_CONST", arg=dummy_code_object),
            TracedInstr("MAKE_FUNCTION", arg=0),
            TracedInstr("STORE_NAME", arg="plus_four"),
            TracedInstr("RETURN_CONST", arg=None),
        )
        call_plus = (
            TracedInstr("PUSH_NULL"),
            TracedInstr("LOAD_FAST", arg="Plus"),
            TracedInstr("CALL", arg=0),
        )
        call_plus_four_int = (
            TracedInstr("LOAD_FAST", arg="plus_0"),
            TracedInstr("LOAD_ATTR", arg=(True, "plus_four")),
            TracedInstr("LOAD_FAST", arg="int_0"),
            TracedInstr("CALL", arg=1),
            # BAD: self.calculations += 1
            TracedInstr("LOAD_FAST", arg="self"),
            TracedInstr("COPY", arg=1),
            TracedInstr("LOAD_ATTR", arg=(False, "calculations")),
            TracedInstr("LOAD_CONST", arg=1),
            TracedInstr("BINARY_OP", arg=BinaryOp.INPLACE_ADD.value),
            TracedInstr("SWAP", arg=2),
            TracedInstr("STORE_ATTR", arg="calculations"),
            # return number + 4
            TracedInstr("LOAD_FAST", arg="number"),
            TracedInstr("LOAD_CONST", arg=4),
            TracedInstr("BINARY_OP", arg=0),
            TracedInstr("RETURN_VALUE"),
        )
        call_plus_four_var = (
            TracedInstr("LOAD_FAST", arg="plus_0"),
            TracedInstr("LOAD_ATTR", arg=(True, "plus_four")),
            TracedInstr("LOAD_FAST", arg="var_1"),
            TracedInstr("CALL", arg=1),
        )
    elif sys.version_info >= (3, 11):
        create_plus = (
            TracedInstr("PUSH_NULL"),
            TracedInstr("LOAD_BUILD_CLASS"),
            TracedInstr("LOAD_CONST", arg=dummy_code_object),
            TracedInstr("MAKE_FUNCTION", arg=0),
            TracedInstr("LOAD_CONST", arg="Plus"),
            TracedInstr("PRECALL", arg=2),
            TracedInstr("CALL", arg=2),
            # BAD: falsely included
            TracedInstr("LOAD_CONST", arg=0),
            TracedInstr("STORE_NAME", arg="calculations"),
            TracedInstr("LOAD_CONST", arg=dummy_code_object),
            TracedInstr("MAKE_FUNCTION", arg=0),
            TracedInstr("STORE_NAME", arg="plus_four"),
            TracedInstr("LOAD_CONST", arg=None),
            TracedInstr("RETURN_VALUE"),
        )
        call_plus = (
            TracedInstr("PUSH_NULL"),
            TracedInstr("LOAD_FAST", arg="Plus"),
            TracedInstr("PRECALL", arg=0),
            TracedInstr("CALL", arg=0),
        )
        call_plus_four_int = (
            TracedInstr("LOAD_FAST", arg="plus_0"),
            TracedInstr("LOAD_METHOD", arg="plus_four"),
            TracedInstr("LOAD_FAST", arg="int_0"),
            TracedInstr("PRECALL", arg=1),
            TracedInstr("CALL", arg=1),
            # BAD: self.calculations += 1
            TracedInstr("LOAD_FAST", arg="self"),
            TracedInstr("COPY", arg=1),
            TracedInstr("LOAD_ATTR", arg="calculations"),
            TracedInstr("LOAD_CONST", arg=1),
            TracedInstr("BINARY_OP", arg=BinaryOp.INPLACE_ADD.value),
            TracedInstr("SWAP", arg=2),
            TracedInstr("STORE_ATTR", arg="calculations"),
            # return number + 4
            TracedInstr("LOAD_FAST", arg="number"),
            TracedInstr("LOAD_CONST", arg=4),
            TracedInstr("BINARY_OP", arg=0),
            TracedInstr("RETURN_VALUE"),
        )
        call_plus_four_var = (
            TracedInstr("LOAD_FAST", arg="plus_0"),
            TracedInstr("LOAD_METHOD", arg="plus_four"),
            TracedInstr("LOAD_FAST", arg="var_1"),
            TracedInstr("PRECALL", arg=1),
            TracedInstr("CALL", arg=1),
        )
    else:
        create_plus = (
            TracedInstr("LOAD_BUILD_CLASS"),
            TracedInstr("LOAD_CONST", arg=dummy_code_object),
            TracedInstr("LOAD_CONST", arg="Plus"),
            TracedInstr("MAKE_FUNCTION", arg=0),
            TracedInstr("LOAD_CONST", arg="Plus"),
            TracedInstr("CALL_FUNCTION", arg=2),
            # BAD: falsely included
            TracedInstr("LOAD_CONST", arg=0),
            TracedInstr("STORE_NAME", arg="calculations"),
            TracedInstr("LOAD_CONST", arg=dummy_code_object),
            TracedInstr(
                "LOAD_CONST", arg="test_data_dependency_6.<locals>.func.<locals>.Plus.plus_four"
            ),
            TracedInstr("MAKE_FUNCTION", arg=0),
            TracedInstr("STORE_NAME", arg="plus_four"),
            TracedInstr("LOAD_CONST", arg=None),
            TracedInstr("RETURN_VALUE"),
        )
        call_plus = (
            TracedInstr("LOAD_FAST", arg="Plus"),
            TracedInstr("CALL_FUNCTION", arg=0),
        )
        call_plus_four_int = (
            TracedInstr("LOAD_FAST", arg="plus_0"),
            TracedInstr("LOAD_METHOD", arg="plus_four"),
            TracedInstr("LOAD_FAST", arg="int_0"),
            TracedInstr("CALL_METHOD", arg=1),
            # BAD: self.calculations += 1
            TracedInstr("LOAD_FAST", arg="self"),
            TracedInstr("DUP_TOP"),
            TracedInstr("LOAD_ATTR", arg="calculations"),
            TracedInstr("LOAD_CONST", arg=1),
            TracedInstr("INPLACE_ADD"),
            TracedInstr("ROT_TWO"),
            TracedInstr("STORE_ATTR", arg="calculations"),
            # return number + 4
            TracedInstr("LOAD_FAST", arg="number"),
            TracedInstr("LOAD_CONST", arg=4),
            binary_add_instruction,
            TracedInstr("RETURN_VALUE"),
        )
        call_plus_four_var = (
            TracedInstr("LOAD_FAST", arg="plus_0"),
            TracedInstr("LOAD_METHOD", arg="plus_four"),
            TracedInstr("LOAD_FAST", arg="var_1"),
            TracedInstr("CALL_METHOD", arg=1),
        )

    expected_instructions = [
        # class Plus:
        *create_plus,
        TracedInstr("STORE_FAST", arg="Plus"),
        # plus_0 = Plus()
        *call_plus,
        TracedInstr("STORE_FAST", arg="plus_0"),
        # int_0 = 42
        TracedInstr(load_const, arg=42),
        TracedInstr("STORE_FAST", arg="int_0"),
        # ... = plus_0.plus_four(int_0)
        *call_plus_four_int,
        # var_1 = ...
        TracedInstr("STORE_FAST", arg="var_1"),
        # return plus_0.plus_four(var_1)
        *call_plus_four_var,
        TracedInstr("RETURN_VALUE"),
    ]

    sliced_instructions = slice_function_at_return(func)
    assert_slice_equal(sliced_instructions, expected_instructions)
