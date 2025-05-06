#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
# Idea and structure are taken from the pyChecco project, see:
# https://github.com/ipsw1/pychecco
# ruff: noqa: E501, ERA001

from bytecode import BasicBlock
from bytecode import CellVar
from bytecode import Compare
from bytecode import FreeVar
from bytecode import Instr

from tests.slicer.util import compare
from tests.slicer.util import dummy_code_object
from tests.slicer.util import slice_function_at_return
from tests.slicer.util import slice_module_at_return


def test_simple_loop():
    def func():
        result = 0
        for i in range(0, 3):  # noqa: PIE808
            result += i
        return result

    return_block = BasicBlock([
        # return result
        Instr("LOAD_FAST", arg="result"),
        Instr("RETURN_VALUE"),
    ])
    loop_header = BasicBlock([
        Instr("FOR_ITER", arg=return_block),
    ])
    loop_block = BasicBlock([
        # result += i
        Instr("STORE_FAST", arg="i"),
        Instr("LOAD_FAST", arg="result"),
        Instr("LOAD_FAST", arg="i"),
        Instr("INPLACE_ADD"),
        Instr("STORE_FAST", arg="result"),
        Instr("JUMP_ABSOLUTE", arg=loop_header),
    ])
    loop_setup = BasicBlock([
        # for i in range(0, 3):
        Instr("LOAD_GLOBAL", arg="range"),
        Instr("LOAD_CONST", arg=0),
        Instr("LOAD_CONST", arg=3),
        Instr("CALL_FUNCTION", arg=2),
        Instr("GET_ITER"),
    ])
    init_block = BasicBlock([
        Instr("LOAD_CONST", arg=0),
        Instr("STORE_FAST", arg="result"),
    ])

    expected_instructions = []
    expected_instructions.extend(init_block)
    expected_instructions.extend(loop_setup)
    expected_instructions.extend(loop_header)
    expected_instructions.extend(loop_block)
    expected_instructions.extend(return_block)

    sliced_instructions = slice_function_at_return(func)
    assert len(sliced_instructions) == len(expected_instructions)
    assert compare(sliced_instructions, expected_instructions)


def test_call_without_arguments():
    module_block = BasicBlock([
        # def callee():
        Instr("LOAD_CONST", arg=dummy_code_object),
        Instr("LOAD_CONST", arg="callee"),
        Instr("MAKE_FUNCTION", arg=0),
        Instr("STORE_NAME", arg="callee"),
        # result = callee()
        Instr("LOAD_GLOBAL", arg="callee"),
        Instr("CALL_FUNCTION", arg=0),
        Instr("STORE_FAST", arg="result"),
        # return result
        Instr("LOAD_FAST", arg="result"),
        Instr("RETURN_VALUE"),
    ])
    callee_block = BasicBlock([Instr("LOAD_CONST", arg=0), Instr("RETURN_VALUE")])

    expected_instructions = []
    expected_instructions.extend(module_block)
    expected_instructions.extend(callee_block)

    module = "tests.fixtures.slicer.simple_call"
    sliced_instructions = slice_module_at_return(module)
    assert len(sliced_instructions) == len(expected_instructions)
    assert compare(sliced_instructions, expected_instructions)


def test_call_with_arguments():
    # Call with two arguments, one of which is used in the callee

    module_block = BasicBlock([
        # def callee():
        Instr("LOAD_CONST", arg="a"),
        Instr("LOAD_NAME", arg="int"),
        Instr("LOAD_CONST", arg="b"),
        Instr("LOAD_NAME", arg="int"),
        Instr("BUILD_TUPLE", arg=4),
        Instr("LOAD_CONST", arg=dummy_code_object),
        Instr("LOAD_CONST", arg="callee"),
        Instr("MAKE_FUNCTION", arg=4),
        Instr("STORE_NAME", arg="callee"),
        # foo = 1
        Instr("LOAD_CONST", arg=1),
        Instr("STORE_FAST", arg="foo"),
        # bar = 2
        Instr("LOAD_CONST", arg=2),
        Instr("STORE_FAST", arg="bar"),
        # result = callee()
        Instr("LOAD_GLOBAL", arg="callee"),
        Instr("LOAD_FAST", arg="foo"),
        Instr("LOAD_FAST", arg="bar"),
        Instr("CALL_FUNCTION", arg=2),
        Instr("STORE_FAST", arg="result"),
        # return result
        Instr("LOAD_FAST", arg="result"),
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
    assert compare(sliced_instructions, expected_instructions)


def test_generators():
    # YIELD_VALUE and YIELD_FROM
    abc_generator = BasicBlock([
        # a = "a"
        Instr("LOAD_CONST", arg="a"),
        Instr("STORE_FAST", arg="a"),
        # yield a
        Instr("LOAD_FAST", arg="a"),
        Instr("YIELD_VALUE"),
    ])

    abc_xyz_generator = BasicBlock([
        # x = "x"
        Instr("LOAD_CONST", arg="x"),
        Instr("STORE_FAST", arg="x"),
        # yield from abc_generator()
        Instr("LOAD_GLOBAL", arg="abc_generator"),
        Instr("CALL_FUNCTION", arg=0),
        Instr("GET_YIELD_FROM_ITER"),
        Instr("LOAD_CONST", arg=None),
        Instr("YIELD_FROM"),
        # yield x
        Instr("LOAD_FAST", arg="x"),
        Instr("YIELD_VALUE"),
    ])

    end_block = BasicBlock([
        # return result
        Instr("LOAD_FAST", arg="result"),
        Instr("RETURN_VALUE"),
    ])
    loop_block = BasicBlock([
        Instr("STORE_FAST", arg="letter"),
    ])
    loop_header = BasicBlock([
        Instr("FOR_ITER", arg=end_block),
    ])
    loop_if_true_block = BasicBlock([
        Instr("LOAD_FAST", arg="result"),
        Instr("LOAD_FAST", arg="letter"),
        Instr("INPLACE_ADD"),
        Instr("STORE_FAST", arg="result"),
        Instr("JUMP_ABSOLUTE", arg=loop_header),
    ])
    loop_if_x_block = BasicBlock([
        Instr("LOAD_FAST", arg="letter"),
        Instr("LOAD_CONST", arg="x"),
        Instr("COMPARE_OP", arg=Compare.EQ),
        Instr("POP_JUMP_IF_TRUE", arg=loop_if_true_block),
    ])
    loop_if_a_block = BasicBlock([
        Instr("LOAD_FAST", arg="letter"),
        Instr("LOAD_CONST", arg="a"),
        Instr("COMPARE_OP", arg=Compare.EQ),
        Instr("POP_JUMP_IF_FALSE", arg=loop_header),
    ])
    module_block = BasicBlock([
        # def abc_generator():
        Instr("LOAD_CONST", arg=dummy_code_object),
        Instr("LOAD_CONST", arg="abc_generator"),
        Instr("MAKE_FUNCTION", arg=0),
        Instr("STORE_NAME", arg="abc_generator"),
        # def abc_xyz_generator():
        Instr("LOAD_CONST", arg=dummy_code_object),
        Instr("LOAD_CONST", arg="abc_xyz_generator"),
        Instr("MAKE_FUNCTION", arg=0),
        Instr("STORE_NAME", arg="abc_xyz_generator"),
        # generator = abc_xyz_generator()
        Instr("LOAD_GLOBAL", arg="abc_xyz_generator"),
        Instr("CALL_FUNCTION", arg=0),
        Instr("STORE_FAST", arg="generator"),
        # result = ""
        Instr("LOAD_CONST", arg=""),
        Instr("STORE_FAST", arg="result"),
        # for letter in generator:
        Instr("LOAD_FAST", arg="generator"),
        Instr("GET_ITER"),
    ])

    expected_instructions = []
    expected_instructions.extend(module_block)
    expected_instructions.extend(loop_header)
    expected_instructions.extend(loop_block)
    expected_instructions.extend(loop_if_x_block)
    expected_instructions.extend(loop_if_a_block)
    expected_instructions.extend(loop_if_true_block)
    expected_instructions.extend(end_block)
    expected_instructions.extend(abc_xyz_generator)
    expected_instructions.extend(abc_generator)

    module = "tests.fixtures.slicer.generator"
    sliced_instructions = slice_module_at_return(module)
    assert len(sliced_instructions) == len(expected_instructions)
    assert compare(sliced_instructions, expected_instructions)


def test_with_extended_arg():
    def func():
        p = [1, 2, 3, 4, 5, 6]
        unused = p  # noqa: F841
        q, r, *_, __ = p  # With extended argument

        result = q, r
        return result  # noqa: RET504

    module_block = BasicBlock([
        # p = [1, 2, 3, 4, 5, 6]
        Instr("BUILD_LIST", arg=0),
        Instr("LOAD_CONST", arg=(1, 2, 3, 4, 5, 6)),
        Instr("LIST_EXTEND", arg=1),
        Instr("STORE_FAST", arg="p"),
        # q, r, *s, t = p
        Instr("LOAD_FAST", arg="p"),
        # Instr("EXTENDED_ARG", arg=1),  # EXTENDED_ARG can not be in a slice
        Instr("UNPACK_EX", arg=258),
        Instr("STORE_FAST", arg="q"),
        Instr("STORE_FAST", arg="r"),
        # result = q
        Instr("LOAD_FAST", arg="q"),
        Instr("LOAD_FAST", arg="r"),
        Instr("BUILD_TUPLE", arg=2),
        Instr("STORE_FAST", arg="result"),
        # return result
        Instr("LOAD_FAST", arg="result"),
        Instr("RETURN_VALUE"),
    ])

    expected_instructions = []
    expected_instructions.extend(module_block)
    sliced_instructions = slice_function_at_return(func)
    assert len(sliced_instructions) == len(expected_instructions)
    assert compare(sliced_instructions, expected_instructions)


def test_nested_class():
    def func():
        # STORE_DEREF, LOAD_CLOSURE, LOAD_CLASSDEREF
        x = []

        class NestedClass:
            y = x

        class_attr = NestedClass.y

        result = class_attr
        return result  # noqa: RET504

    freevar_x = FreeVar("x")
    cellvar_x = CellVar("x")
    function_block = BasicBlock([
        # x = []
        Instr("BUILD_LIST", arg=0),
        Instr("STORE_DEREF", arg=cellvar_x),
        # class NestedClass:
        Instr("LOAD_BUILD_CLASS"),
        Instr("LOAD_CLOSURE", arg=cellvar_x),
        Instr("BUILD_TUPLE", arg=1),
        Instr("LOAD_CONST", arg=dummy_code_object),
        Instr("LOAD_CONST", arg="NestedClass"),
        Instr("MAKE_FUNCTION", arg=8),
        Instr("LOAD_CONST", arg="NestedClass"),
        Instr("CALL_FUNCTION", arg=2),
        Instr("STORE_FAST", arg="NestedClass"),
        # class_attr = NestedClass.y
        Instr("LOAD_FAST", arg="NestedClass"),
        Instr("LOAD_ATTR", arg="y"),
        Instr("STORE_FAST", arg="class_attr"),
        # result = class_attr
        Instr("LOAD_FAST", arg="class_attr"),
        Instr("STORE_FAST", arg="result"),
        # return result
        Instr("LOAD_FAST", arg="result"),
        Instr("RETURN_VALUE"),
    ])

    nested_class_block = BasicBlock([
        # y = x
        Instr("LOAD_CLASSDEREF", arg=freevar_x),
        Instr("STORE_NAME", arg="y"),
        Instr("LOAD_CONST", arg=None),
        Instr("RETURN_VALUE"),
    ])

    expected_instructions = []
    expected_instructions.extend(function_block)
    expected_instructions.extend(nested_class_block)
    sliced_instructions = slice_function_at_return(func)
    assert len(sliced_instructions) == len(expected_instructions)
    assert compare(sliced_instructions, expected_instructions)


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
    cellvar_x1 = CellVar("x1")
    freevar_x2 = FreeVar("x2")
    cellvar_x2 = CellVar("x2")
    function_block = BasicBlock([
        # x1 = [1]
        Instr("LOAD_CONST", arg=1),
        Instr("BUILD_LIST", arg=1),
        Instr("STORE_DEREF", arg=cellvar_x1),
        # x2 = [2]
        Instr("LOAD_CONST", arg=2),
        Instr("BUILD_LIST", arg=1),
        Instr("STORE_DEREF", arg=cellvar_x2),
        # class Bar:
        Instr("LOAD_BUILD_CLASS"),
        Instr("LOAD_CLOSURE", arg=cellvar_x1),
        Instr("LOAD_CLOSURE", arg=freevar_x2),
        Instr("BUILD_TUPLE", arg=2),
        Instr("LOAD_CONST", arg=dummy_code_object),
        Instr("LOAD_CONST", arg="Bar"),
        Instr("MAKE_FUNCTION", arg=8),
        Instr("LOAD_CONST", arg="Bar"),
        Instr("CALL_FUNCTION", arg=2),
        Instr("STORE_FAST", arg="Bar"),
        # class_attr = Bar.y
        Instr("LOAD_FAST", arg="Bar"),
        Instr("LOAD_ATTR", arg="foo"),
        Instr("STORE_FAST", arg="class_attr"),
        # class_attr2 = Bar.Foo.y
        Instr("LOAD_FAST", arg="Bar"),
        Instr("LOAD_ATTR", arg="Foo"),
        Instr("LOAD_ATTR", arg="y"),
        Instr("STORE_FAST", arg="class_attr2"),
        # result = class_attr + class_attr2
        Instr("LOAD_FAST", arg="class_attr"),
        Instr("LOAD_FAST", arg="class_attr2"),
        Instr("BINARY_ADD"),
        Instr("STORE_FAST", arg="result"),
        # return result
        Instr("LOAD_FAST", arg="result"),
        Instr("RETURN_VALUE"),
    ])

    bar_block = BasicBlock([
        # class Foo:
        Instr("LOAD_BUILD_CLASS"),
        Instr("LOAD_CLOSURE", arg=cellvar_x2),
        Instr("BUILD_TUPLE", arg=1),
        Instr("LOAD_CONST", arg=dummy_code_object),
        Instr("LOAD_CONST", arg="Foo"),
        Instr("MAKE_FUNCTION", arg=8),
        Instr("LOAD_CONST", arg="Foo"),
        Instr("CALL_FUNCTION", arg=2),
        Instr("STORE_NAME", arg="Foo"),
        # foo = x1
        Instr("LOAD_CLASSDEREF", arg=freevar_x1),
        Instr("STORE_NAME", arg="foo"),
        Instr("LOAD_CONST", arg=None),
        Instr("RETURN_VALUE"),
    ])

    foo_block = BasicBlock([
        # y = x2
        Instr("LOAD_CLASSDEREF", arg=freevar_x2),
        Instr("STORE_NAME", arg="y"),
        Instr("LOAD_CONST", arg=None),
        Instr("RETURN_VALUE"),
    ])

    expected_instructions = []
    expected_instructions.extend(function_block)
    expected_instructions.extend(foo_block)
    expected_instructions.extend(bar_block)
    sliced_instructions = slice_function_at_return(func)
    assert func() == [1, 2]
    assert len(sliced_instructions) == len(expected_instructions)
    assert compare(sliced_instructions, expected_instructions)


def test_lambda():
    def func():
        x = lambda a: a + 10  # noqa: E731

        result = x(1)
        return result  # noqa: RET504

    function_block = BasicBlock([
        # x = lambda a: a + 10
        Instr("LOAD_CONST", arg=dummy_code_object),
        Instr("LOAD_CONST", arg="test_lambda.<locals>.func.<locals>.<lambda>"),
        Instr("MAKE_FUNCTION", arg=0),
        Instr("STORE_FAST", arg="x"),
        # result = x(1)
        Instr("LOAD_FAST", arg="x"),
        Instr("LOAD_CONST", arg=1),
        Instr("CALL_FUNCTION", arg=1),
        Instr("STORE_FAST", arg="result"),
        # return result
        Instr("LOAD_FAST", arg="result"),
        Instr("RETURN_VALUE"),
    ])

    lambda_block = BasicBlock([
        # lambda a: a + 10
        Instr("LOAD_FAST", arg="a"),
        Instr("LOAD_CONST", arg=10),
        Instr("BINARY_ADD"),
        Instr("RETURN_VALUE"),
    ])

    expected_instructions = []
    expected_instructions.extend(function_block)
    expected_instructions.extend(lambda_block)
    sliced_instructions = slice_function_at_return(func)
    assert len(sliced_instructions) == len(expected_instructions)
    assert compare(sliced_instructions, expected_instructions)


def test_builtin_addresses():
    def func():
        test_dict = {1: "one", 2: "two"}
        # noinspection PyListCreation
        test_list = [1, 2]

        test_list.append(3)

        result = test_dict.get(1)
        return result  # noqa: RET504

    function_block = BasicBlock([
        # test_dict = {1: "one", 2: "two"}
        Instr("LOAD_CONST", arg="one"),
        Instr("LOAD_CONST", arg="two"),
        Instr("LOAD_CONST", arg=(1, 2)),
        Instr("BUILD_CONST_KEY_MAP", arg=2),
        Instr("STORE_FAST", arg="test_dict"),
        # result = test_dict.get(1)
        Instr("LOAD_FAST", arg="test_dict"),
        Instr("LOAD_METHOD", arg="get"),
        Instr("LOAD_CONST", arg=1),
        Instr("CALL_METHOD", arg=1),
        Instr("STORE_FAST", arg="result"),
        # return result
        Instr("LOAD_FAST", arg="result"),
        Instr("RETURN_VALUE"),
    ])

    expected_instructions = []
    expected_instructions.extend(function_block)
    sliced_instructions = slice_function_at_return(func)
    assert len(sliced_instructions) == len(expected_instructions)
    assert compare(sliced_instructions, expected_instructions)


def test_data_dependency_immutable_attribute():
    # Explicit attribute dependency of immutable type
    module_block = BasicBlock([
        # class Foo:
        Instr("LOAD_BUILD_CLASS"),
        Instr("LOAD_CONST", arg=dummy_code_object),
        Instr("LOAD_CONST", arg="Foo"),
        Instr("MAKE_FUNCTION", arg=0),
        Instr("LOAD_CONST", arg="Foo"),
        Instr("CALL_FUNCTION", arg=2),
        Instr("STORE_NAME", arg="Foo"),
        # result = ob.attr
        Instr("LOAD_FAST", arg="ob"),
        Instr("LOAD_ATTR", arg="attr"),
        Instr("STORE_FAST", arg="result"),
        Instr("LOAD_FAST", arg="result"),
        Instr("RETURN_VALUE"),
    ])
    class_attr_block = BasicBlock([
        # attr = 1
        Instr("LOAD_CONST", arg=1),
        Instr("STORE_NAME", arg="attr"),
        Instr("LOAD_CONST", arg=None),
        Instr("RETURN_VALUE"),
    ])

    expected_instructions = []
    expected_instructions.extend(module_block)
    expected_instructions.extend(class_attr_block)

    module = "tests.fixtures.slicer.immutable_attribute_dependency"
    sliced_instructions = slice_module_at_return(module)
    assert len(sliced_instructions) == len(expected_instructions)
    assert compare(sliced_instructions, expected_instructions)


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

    function_block = BasicBlock([
        # class NestedClass:
        Instr("LOAD_BUILD_CLASS"),
        Instr("LOAD_CONST", arg=dummy_code_object),
        Instr("LOAD_CONST", arg="NestedClass"),
        Instr("MAKE_FUNCTION", arg=0),
        Instr("LOAD_CONST", arg="NestedClass"),
        Instr("CALL_FUNCTION", arg=2),
        Instr("STORE_FAST", arg="NestedClass"),
        # ob = NestedClass()
        Instr("LOAD_FAST", arg="NestedClass"),
        Instr("CALL_FUNCTION", arg=0),
        Instr("STORE_FAST", arg="ob"),
        # ob.inc_x()
        Instr("LOAD_FAST", arg="ob"),
        Instr("LOAD_METHOD", arg="inc_x"),
        Instr("CALL_METHOD", arg=0),
        # result = ob.x
        Instr("LOAD_FAST", arg="ob"),
        Instr("LOAD_ATTR", arg="x"),
        Instr("STORE_FAST", arg="result"),
        # return result
        Instr("LOAD_FAST", arg="result"),
        Instr("RETURN_VALUE"),
    ])

    nested_class_block = BasicBlock([
        # Definition of dunder methods are wrongly excluded, since these are not explicitly loaded
        # def __init__(self):
        # Instr("LOAD_CONST", arg=dummy_code_object),
        # Instr("LOAD_CONST", arg="IntegrationTestLanguageFeatures.test_object_modification_call.<locals>."
        #                         "func.<locals>.NestedClass.__init__"),
        # Instr("MAKE_FUNCTION", arg=0),
        # Instr("STORE_NAME", arg="__init__"),
        # def inc_x(self):
        Instr("LOAD_CONST", arg=dummy_code_object),
        Instr(
            "LOAD_CONST",
            arg="test_object_modification_call.<locals>.func.<locals>.NestedClass.inc_x",
        ),
        Instr("MAKE_FUNCTION", arg=0),
        Instr("STORE_NAME", arg="inc_x"),
        Instr("LOAD_CONST", arg=None),
        Instr("RETURN_VALUE"),
    ])

    init_block = BasicBlock([
        # self.x = 1
        Instr("LOAD_CONST", arg=1),
        Instr("LOAD_FAST", arg="self"),
        Instr("STORE_ATTR", arg="x"),
        Instr("LOAD_CONST", arg=None),
        Instr("RETURN_VALUE"),
    ])

    inc_x_block = BasicBlock([
        # self.x = self.x + 1
        Instr("LOAD_FAST", arg="self"),
        Instr("LOAD_ATTR", arg="x"),
        Instr("LOAD_CONST", arg=1),
        Instr("BINARY_ADD"),
        Instr("LOAD_FAST", arg="self"),
        Instr("STORE_ATTR", arg="x"),
    ])

    expected_instructions = []
    expected_instructions.extend(function_block)
    expected_instructions.extend(nested_class_block)
    expected_instructions.extend(init_block)
    expected_instructions.extend(inc_x_block)
    sliced_instructions = slice_function_at_return(func)
    assert len(sliced_instructions) == len(expected_instructions)
    assert compare(sliced_instructions, expected_instructions)


def test_closures():
    # Closure function

    freevar_foo = FreeVar("foo")
    cellvar_foo = CellVar("foo")
    module_block = BasicBlock([
        # def outer_function(foo):
        Instr("LOAD_CONST", arg=dummy_code_object),
        Instr("LOAD_CONST", arg="outer_function"),
        Instr("MAKE_FUNCTION", arg=0),
        Instr("STORE_NAME", arg="outer_function"),
        # inner = outer_function('a')
        Instr("LOAD_GLOBAL", arg="outer_function"),
        Instr("LOAD_CONST", arg="a"),
        Instr("CALL_FUNCTION", arg=1),
        Instr("STORE_FAST", arg="inner"),
        # result = inner("abc")
        Instr("LOAD_FAST", arg="inner"),
        Instr("LOAD_CONST", arg="abc"),
        Instr("CALL_FUNCTION", arg=1),
        Instr("STORE_FAST", arg="result"),
        Instr("LOAD_FAST", arg="result"),
        Instr("RETURN_VALUE"),
    ])
    outer_function_block = BasicBlock([
        # def inner_function(bar):
        Instr("LOAD_CLOSURE", arg=cellvar_foo),
        Instr("BUILD_TUPLE", arg=1),
        Instr("LOAD_CONST", arg=dummy_code_object),
        Instr("LOAD_CONST", arg="outer_function.<locals>.inner_function"),
        Instr("MAKE_FUNCTION", arg=8),
        Instr("STORE_FAST", arg="inner_function"),
        # return inner
        Instr("LOAD_FAST", arg="inner_function"),
        Instr("RETURN_VALUE"),
    ])
    inner_function_block = BasicBlock([
        # return foo in bar
        Instr("LOAD_DEREF", arg=freevar_foo),
        Instr("LOAD_FAST", arg="bar"),
        Instr("CONTAINS_OP", arg=0),
        Instr("RETURN_VALUE"),
    ])

    expected_instructions = []
    expected_instructions.extend(module_block)
    expected_instructions.extend(outer_function_block)
    expected_instructions.extend(inner_function_block)

    module = "tests.fixtures.slicer.closure"
    sliced_instructions = slice_module_at_return(module)
    assert len(sliced_instructions) == len(expected_instructions)
    assert compare(sliced_instructions, expected_instructions)
