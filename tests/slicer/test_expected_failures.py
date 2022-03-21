#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
# Idea and structure are taken from the pyChecco project, see:
# https://github.com/ipsw1/pychecco

import os

from bytecode import BasicBlock, Compare, Instr

from tests.slicer.util import (
    compare,
    compile_module,
    dummy_code_object,
    instrument_module,
    slice_function_at_return,
    slice_module_at_return,
)

# TODO(SiL) adjust paths
path_sep = os.path.sep
example_modules_directory = "example_modules/"
example_modules_path = (
    path_sep.join(__file__.split(path_sep)[:-1]) + path_sep + example_modules_directory
)


# TODO(SiL) was marked as 'ExpectedFailure', how to adjust?
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

        result = foo_list[0]  # correctly included
        return result  # correctly included

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

    dynamic_slice = slice_function_at_return(func)
    assert len(dynamic_slice.sliced_instructions) == len(expected_instructions)
    assert compare(dynamic_slice.sliced_instructions, expected_instructions)


# TODO(SiL) was marked as 'ExpectedFailure', how to adjust?
def test_dunder_definition():
    def func():
        class NestedClass:
            def __init__(
                self,
            ):  # Definition of dunder methods wrongly excluded, these are not explicitly loaded
                self.x = 1

        result = NestedClass()
        return result

    function_block = BasicBlock(
        [
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
        ]
    )

    nested_class_block = BasicBlock(
        [
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
        ]
    )

    init_block = BasicBlock(
        [
            # .x = 1
            Instr("LOAD_CONST", arg=1),
            Instr("LOAD_FAST", arg=""),
            Instr("STORE_ATTR", arg="x"),
            Instr("LOAD_CONST", arg=None),
            Instr("RETURN_VALUE"),
        ]
    )

    expected_instructions = []
    expected_instructions.extend(function_block)
    expected_instructions.extend(nested_class_block)
    expected_instructions.extend(init_block)
    dynamic_slice = slice_function_at_return(func)
    assert len(dynamic_slice.sliced_instructions) == len(expected_instructions)
    assert compare(dynamic_slice.sliced_instructions, expected_instructions)


# TODO(SiL) was marked as 'ExpectedFailure', how to adjust?
def test_mod_untraced_object():
    def func():
        lst = [("foo", "3"), ("bar", "1"), ("foobar", "2")]
        lst.sort()  # This is incorrectly excluded, since it is not known that the method modifies the list

        result = lst
        return result

    function_block = BasicBlock(
        [
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
        ]
    )

    expected_instructions = []
    expected_instructions.extend(function_block)
    dynamic_slice = slice_function_at_return(func)
    assert len(dynamic_slice.sliced_instructions) == len(expected_instructions)
    assert compare(dynamic_slice.sliced_instructions, expected_instructions)


# TODO(SiL) was marked as 'ExpectedFailure', how to adjust?
def test_call_unused_argument():
    # Call with two arguments, one of which is used in the callee

    module_block = BasicBlock(
        [
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
        ]
    )
    callee_block = BasicBlock(
        [
            # return a
            Instr("LOAD_FAST", arg="a"),
            Instr("RETURN_VALUE"),
        ]
    )

    expected_instructions = []
    expected_instructions.extend(module_block)
    expected_instructions.extend(callee_block)

    # TODO(SiL) adjust paths
    module_file = "simple_call_arg.py"
    module_path = example_modules_path + module_file
    dynamic_slice = slice_module_at_return(module_path)
    assert len(dynamic_slice.sliced_instructions) == len(expected_instructions)
    assert compare(dynamic_slice.sliced_instructions, expected_instructions)


# TODO(SiL) was marked as 'ExpectedFailure', how to adjust?
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

    return_block = BasicBlock(
        [
            # return result
            Instr("LOAD_FAST", arg="result"),
            Instr("RETURN_VALUE"),
        ]
    )
    try_block = BasicBlock(
        [
            # result = foo / bar <- did somehow effect slicing criterion...
            Instr("LOAD_FAST", arg="foo"),
            Instr("LOAD_FAST", arg="bar"),
            Instr("BINARY_TRUE_DIVIDE"),
            # except ZeroDivisionError:
            Instr("DUP_TOP"),
            Instr("LOAD_GLOBAL", arg="ZeroDivisionError"),
            Instr("COMPARE_OP", arg=Compare.EXC_MATCH),
            Instr("POP_JUMP_IF_FALSE", arg=dummy_block),
        ]
    )
    except_block = BasicBlock(
        [
            # result = foo + bar
            Instr("LOAD_FAST", arg="foo"),
            Instr("LOAD_FAST", arg="bar"),
            Instr("BINARY_ADD"),
            Instr("STORE_FAST", arg="result"),
            Instr("JUMP_FORWARD", arg=dummy_block),
        ]
    )
    function_block = BasicBlock(
        [
            # foo = 1
            Instr("LOAD_CONST", arg=1),  # <- excluded because no stack simulation
            Instr("STORE_FAST", arg="foo"),
            # bar = 0
            Instr("LOAD_CONST", arg=0),  # <- excluded because no stack simulation
            Instr("STORE_FAST", arg="bar"),
            # try:
            # Instr("SETUP_FINALLY", arg=try_block),
        ]
    )

    expected_instructions = []
    expected_instructions.extend(return_block)
    expected_instructions.extend(except_block)
    expected_instructions.extend(function_block)
    expected_instructions.extend(try_block)

    dynamic_slice = slice_function_at_return(func)
    assert len(dynamic_slice.sliced_instructions) == len(expected_instructions)
    assert compare(dynamic_slice.sliced_instructions, expected_instructions)


# TODO(SiL) was marked as 'ExpectedFailure', how to adjust?
def test_import_star():
    # IMPORT_STAR with access to immutable variable
    main_module_block = BasicBlock(
        [
            # TODO(SiL) adjust paths
            # from tests.slicer.example_modules.import_star_def import *
            Instr("IMPORT_NAME", "tests.slicer.example_modules.import_star_def"),
            Instr("IMPORT_STAR"),
            # result = Foo.test
            Instr("LOAD_NAME", arg="star_imported"),
            Instr("STORE_NAME", arg="result"),
            Instr("LOAD_CONST", arg=None),
            Instr("RETURN_VALUE"),
        ]
    )
    dependency_module_block = BasicBlock(
        [
            # star_imported = "test"
            Instr("LOAD_CONST", arg="test"),
            Instr("STORE_NAME", arg="star_imported"),
            Instr("LOAD_CONST", arg=None),
            Instr("RETURN_VALUE"),
        ]
    )

    expected_instructions = []
    expected_instructions.extend(main_module_block)
    expected_instructions.extend(dependency_module_block)

    # TODO(SiL) adjust paths
    module_dependency_file = "import_star_def.py"
    module_dependency_path = example_modules_path + module_dependency_file
    instrument_module(module_dependency_path)

    # TODO(SiL) adjust paths
    module_file = "import_star_main.py"
    module_path = example_modules_path + module_file
    dynamic_slice = slice_module_at_return(module_path)

    compile_module(module_dependency_path)
    assert len(dynamic_slice.sliced_instructions) == len(expected_instructions)
    assert compare(dynamic_slice.sliced_instructions, expected_instructions)
