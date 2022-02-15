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

path_sep = os.path.sep
example_modules_directory = "../fixtures/slicer"
example_modules_path = (
    path_sep.join(__file__.split(path_sep)[:-1]) + path_sep + example_modules_directory
)


def test_data_dependency_1():
    # Implicit data dependency at return, explicit (full cover) for result
    def func() -> int:
        result = 1
        return result

    expected_instructions = [
        # result = 1
        Instr("LOAD_CONST", arg=1),
        Instr("STORE_FAST", arg="result"),
        # return result
        Instr("LOAD_FAST", arg="result"),
        Instr("RETURN_VALUE"),
    ]

    dynamic_slice = slice_function_at_return(func.__code__)
    assert len(dynamic_slice.sliced_instructions) == len(expected_instructions)
    assert compare(dynamic_slice.sliced_instructions, expected_instructions)


def test_data_dependency_2():
    # Implicit data dependency at return, explicit (full cover) for result; foo must be excluded
    def func() -> int:
        result = 1
        foo = 2  # noqa
        return result

    expected_instructions = [
        # result = 1
        Instr("LOAD_CONST", arg=1),
        Instr("STORE_FAST", arg="result"),
        # return result
        Instr("LOAD_FAST", arg="result"),
        Instr("RETURN_VALUE"),
    ]

    dynamic_slice = slice_function_at_return(func.__code__)
    assert len(dynamic_slice.sliced_instructions) == len(expected_instructions)
    assert compare(dynamic_slice.sliced_instructions, expected_instructions)


def test_data_dependency_3():
    # Transitive explicit (full cover) dependencies
    def func() -> int:
        foo = 1
        result = 1 + foo
        return result

    expected_instructions = [
        # foo = 1
        Instr("LOAD_CONST", arg=1),
        Instr("STORE_FAST", arg="foo"),
        # result = 1 + foo
        Instr("LOAD_CONST", arg=1),
        Instr("LOAD_FAST", arg="foo"),
        Instr("BINARY_ADD"),
        Instr("STORE_FAST", arg="result"),
        # return result
        Instr("LOAD_FAST", arg="result"),
        Instr("RETURN_VALUE"),
    ]

    dynamic_slice = slice_function_at_return(func.__code__)
    assert len(dynamic_slice.sliced_instructions) == len(expected_instructions)
    assert compare(dynamic_slice.sliced_instructions, expected_instructions)


def test_data_dependency_4():
    # Explicit attribute dependencies (full cover)
    module_block = BasicBlock(
        [
            # class Foo:
            Instr("LOAD_BUILD_CLASS"),
            Instr("LOAD_CONST", arg=dummy_code_object),
            Instr("LOAD_CONST", arg="Foo"),
            Instr("MAKE_FUNCTION", arg=0),
            Instr("LOAD_CONST", arg="Foo"),
            Instr("CALL_FUNCTION", arg=2),
            Instr("STORE_NAME", arg="Foo"),
            # ob.attr1 = 1
            Instr("LOAD_CONST", arg=1),
            Instr("LOAD_NAME", arg="ob"),
            Instr("STORE_ATTR", arg="attr1"),
            # ob.attr2 = ob.attr2.append(ob.attr1)
            Instr("LOAD_NAME", arg="ob"),
            Instr("LOAD_ATTR", arg="attr2"),
            Instr("LOAD_METHOD", arg="append"),
            Instr("LOAD_NAME", arg="ob"),
            Instr("LOAD_ATTR", arg="attr1"),
            Instr("CALL_METHOD", arg=1),
            Instr("LOAD_NAME", arg="ob"),
            Instr("STORE_ATTR", arg="attr2"),
            # result = ob.attr2
            Instr("LOAD_NAME", arg="ob"),
            Instr("LOAD_ATTR", arg="attr2"),
            Instr("STORE_NAME", arg="result"),
            # return
            Instr("LOAD_CONST", arg=None),
            Instr("RETURN_VALUE"),
        ]
    )
    class_attr_block = BasicBlock(
        [
            # attr2 = [1, 2, 3]
            Instr("LOAD_CONST", arg=1),
            Instr("LOAD_CONST", arg=2),
            Instr("LOAD_CONST", arg=3),
            Instr("BUILD_LIST", arg=3),
            Instr("STORE_NAME", arg="attr2"),
            # return
            Instr("LOAD_CONST", arg=None),
            Instr("RETURN_VALUE"),
        ]
    )

    expected_instructions = []
    expected_instructions.extend(module_block)
    expected_instructions.extend(class_attr_block)

    module_file = "attribute_dependencies.py"
    module_path = example_modules_path + module_file
    dynamic_slice = slice_module_at_return(module_path)
    assert len(dynamic_slice.sliced_instructions) == len(expected_instructions)
    assert compare(dynamic_slice.sliced_instructions, expected_instructions)


def test_data_dependency_5():
    # Explicit attribute dependencies (partial and full cover)
    module_block = BasicBlock(
        [
            # class Foo:
            Instr("LOAD_BUILD_CLASS"),
            Instr("LOAD_CONST", arg=dummy_code_object),
            Instr("LOAD_CONST", arg="Foo"),
            Instr("MAKE_FUNCTION", arg=0),
            Instr("LOAD_CONST", arg="Foo"),
            Instr("CALL_FUNCTION", arg=2),
            Instr("STORE_NAME", arg="Foo"),
            # ob = Foo()
            Instr("LOAD_NAME", arg="Foo"),
            Instr("CALL_FUNCTION", arg=0),
            Instr("STORE_NAME", arg="ob"),
            # ob.attr1 = 1
            Instr("LOAD_CONST", arg=1),
            Instr("LOAD_NAME", arg="ob"),
            Instr("STORE_ATTR", arg="attr1"),
            # result = ob
            Instr("LOAD_NAME", arg="ob"),
            Instr("STORE_NAME", arg="result"),
            # return
            Instr("LOAD_CONST", arg=None),
            Instr("RETURN_VALUE"),
        ]
    )
    class_attr_block = BasicBlock(
        [Instr("LOAD_CONST", arg=None), Instr("RETURN_VALUE")]
    )

    expected_instructions = []
    expected_instructions.extend(module_block)
    expected_instructions.extend(class_attr_block)

    module_file = "partial_cover_dependency.py"
    module_path = example_modules_path + module_file
    dynamic_slice = slice_module_at_return(module_path)
    assert len(dynamic_slice.sliced_instructions) == len(expected_instructions)
    assert compare(dynamic_slice.sliced_instructions, expected_instructions)


def test_data_dependency_6():
    # Data dependencies across modules (explicit, full cover)
    main_module_block = BasicBlock(
        [
            # from tests.slicer.integration.example_modules.module_dependency_def import module_list, Foo
            Instr("LOAD_CONST", arg=0),
            Instr("LOAD_CONST", arg=("module_list", "unused_list", "Foo")),
            Instr(
                "IMPORT_NAME", arg="tests.slicer.example_modules.module_dependency_def"
            ),
            Instr("IMPORT_FROM", arg="module_list"),
            Instr("STORE_NAME", arg="module_list"),
            # Instr("IMPORT_FROM", arg="unused_list"),
            # Instr("STORE_NAME", arg="unused_list"),
            Instr("IMPORT_FROM", arg="Foo"),
            Instr("STORE_NAME", arg="Foo"),
            # result = module_list + Foo.get_class_list()
            Instr("LOAD_NAME", arg="module_list"),
            Instr("LOAD_NAME", arg="Foo"),
            Instr("LOAD_METHOD", arg="get_class_list"),
            Instr("CALL_METHOD", arg=0),
            Instr("BINARY_ADD"),
            Instr("STORE_NAME", arg="result"),
            # return
            Instr("LOAD_CONST", arg=None),
            Instr("RETURN_VALUE"),
        ]
    )
    dependency_module_block = BasicBlock(
        [
            # module_list = [1, 2, 3]
            Instr("LOAD_CONST", arg=1),
            Instr("LOAD_CONST", arg=2),
            Instr("LOAD_CONST", arg=3),
            Instr("BUILD_LIST", arg=3),
            Instr("STORE_NAME", arg="module_list"),
            # class Foo:
            Instr("LOAD_BUILD_CLASS"),
            Instr("LOAD_CONST", arg=dummy_code_object),
            Instr("LOAD_CONST", arg="Foo"),
            Instr("MAKE_FUNCTION", arg=0),
            Instr("LOAD_CONST", arg="Foo"),
            Instr("CALL_FUNCTION", arg=2),
            Instr("STORE_NAME", arg="Foo"),
            # class_list = [4, 5, 6]
            Instr("LOAD_CONST", arg=7),
            Instr("LOAD_CONST", arg=8),
            Instr("LOAD_CONST", arg=9),
            Instr("BUILD_LIST", arg=3),
            Instr("STORE_NAME", arg="class_list"),
            # @staticmethod
            Instr("LOAD_NAME", arg="staticmethod"),
            # def get_class_list():
            Instr("LOAD_CONST", arg=dummy_code_object),
            Instr("LOAD_CONST", arg="Foo.get_class_list"),
            Instr("MAKE_FUNCTION", arg=0),
            Instr("CALL_FUNCTION", arg=1),
            Instr("STORE_NAME", arg="get_class_list"),
            # return Foo.class_list
            Instr("LOAD_GLOBAL", arg="Foo"),
            Instr("LOAD_ATTR", arg="class_list"),
            Instr("RETURN_VALUE"),
            Instr("LOAD_CONST", arg=None),
            Instr("RETURN_VALUE"),
            Instr("LOAD_CONST", arg=None),
            Instr("RETURN_VALUE"),
        ]
    )

    expected_instructions = []
    expected_instructions.extend(main_module_block)
    expected_instructions.extend(dependency_module_block)

    module_dependency_file = "module_dependency_def.py"
    module_dependency_path = example_modules_path + module_dependency_file
    instrument_module(module_dependency_path)

    module_file = "module_dependency_main.py"
    module_path = example_modules_path + module_file
    dynamic_slice = slice_module_at_return(module_path)

    compile_module(module_dependency_path)
    assert len(dynamic_slice.sliced_instructions) == len(expected_instructions)
    assert compare(dynamic_slice.sliced_instructions, expected_instructions)


def test_simple_control_dependency_1():
    # If condition evaluated to true, with relevant variable foo
    def func() -> int:
        foo = 1
        result = 3

        if foo == 1:
            result = 1

        return result

    return_basic_block = BasicBlock(
        [
            # return result
            Instr("LOAD_FAST", arg="result"),
            Instr("RETURN_VALUE"),
        ]
    )
    if_basic_block = BasicBlock(
        [
            # result = 1
            Instr("LOAD_CONST", arg=1),
            Instr("STORE_FAST", arg="result"),
        ]
    )
    init_basic_block = BasicBlock(
        [
            # foo = 1
            Instr("LOAD_CONST", arg=1),
            Instr("STORE_FAST", arg="foo"),
            # if foo == 1
            Instr("LOAD_FAST", arg="foo"),
            Instr("LOAD_CONST", arg=1),
            Instr("COMPARE_OP", arg=Compare.EQ),
            Instr("POP_JUMP_IF_FALSE", arg=return_basic_block),
        ]
    )

    expected_instructions = []
    expected_instructions.extend(init_basic_block)
    expected_instructions.extend(if_basic_block)
    expected_instructions.extend(return_basic_block)

    dynamic_slice = slice_function_at_return(func.__code__)
    assert len(dynamic_slice.sliced_instructions) == len(expected_instructions)
    assert compare(dynamic_slice.sliced_instructions, expected_instructions)


def test_simple_control_dependency_2():
    # If condition evaluated to false, with two relevant variables (but no influence on result)
    def func() -> int:
        foo = 1
        bar = 2
        result = 3

        if foo == bar:
            result = 1

        return result

    init_basic_block = BasicBlock(
        [
            # result = 3
            Instr("LOAD_CONST", arg=3),
            Instr("STORE_FAST", arg="result"),
        ]
    )
    return_basic_block = BasicBlock(
        [
            # return result
            Instr("LOAD_FAST", arg="result"),
            Instr("RETURN_VALUE"),
        ]
    )

    expected_instructions = []
    expected_instructions.extend(init_basic_block)
    expected_instructions.extend(return_basic_block)

    dynamic_slice = slice_function_at_return(func.__code__)
    assert len(dynamic_slice.sliced_instructions) == len(expected_instructions)
    assert compare(dynamic_slice.sliced_instructions, expected_instructions)


def test_simple_control_dependency_3():
    # If-elif-else with elif branch true
    def func() -> int:
        foo = 1
        bar = 2

        if foo == bar:
            result = 1
        elif foo == 1:
            result = 2
        else:
            result = 3

        return result

    return_block = BasicBlock(
        [
            # return result
            Instr("LOAD_FAST", arg="result"),
            Instr("RETURN_VALUE"),
        ]
    )
    elif_block = BasicBlock(
        [
            # result = 2
            Instr("LOAD_CONST", arg=2),
            Instr("STORE_FAST", arg="result"),
            Instr("JUMP_FORWARD", arg=return_block),
        ]
    )
    elif_cond = BasicBlock(
        [
            # elif foo == 1:
            Instr("LOAD_FAST", arg="foo"),
            Instr("LOAD_CONST", arg=1),
            Instr("COMPARE_OP", arg=Compare.EQ),
            Instr("POP_JUMP_IF_FALSE", arg=elif_block),
        ]
    )
    if_cond = BasicBlock(
        [
            # if foo == bar
            Instr("LOAD_FAST", arg="foo"),
            Instr("LOAD_FAST", arg="bar"),
            Instr("COMPARE_OP", arg=Compare.EQ),
            Instr("POP_JUMP_IF_FALSE", arg=elif_cond),
        ]
    )
    init_block = BasicBlock(
        [
            # foo = 1
            Instr("LOAD_CONST", arg=1),
            Instr("STORE_FAST", arg="foo"),
            # bar = 2
            Instr("LOAD_CONST", arg=2),
            Instr("STORE_FAST", arg="bar"),
        ]
    )

    expected_instructions = []
    expected_instructions.extend(init_block)
    expected_instructions.extend(if_cond)
    expected_instructions.extend(elif_cond)
    expected_instructions.extend(elif_block)
    expected_instructions.extend(return_block)

    dynamic_slice = slice_function_at_return(func.__code__)
    assert len(dynamic_slice.sliced_instructions) == len(expected_instructions)
    assert compare(dynamic_slice.sliced_instructions, expected_instructions)


def test_simple_control_dependency_4():
    # If-elif-else with else branch true
    def func() -> int:
        foo = 1
        bar = 2

        if foo == bar:
            result = 1
        elif foo > bar:
            result = 2
        else:
            result = 3

        return result

    return_block = BasicBlock(
        [
            # return result
            Instr("LOAD_FAST", arg="result"),
            Instr("RETURN_VALUE"),
        ]
    )
    else_block = BasicBlock(
        [
            # result = 3
            Instr("LOAD_CONST", arg=3),
            Instr("STORE_FAST", arg="result"),
        ]
    )
    elif_cond = BasicBlock(
        [
            # elif foo == 1:
            Instr("LOAD_FAST", arg="foo"),
            Instr("LOAD_FAST", arg="bar"),
            Instr("COMPARE_OP", arg=Compare.GT),
            Instr("POP_JUMP_IF_FALSE", arg=else_block),
        ]
    )
    if_cond = BasicBlock(
        [
            # if foo == bar
            Instr("LOAD_FAST", arg="foo"),
            Instr("LOAD_FAST", arg="bar"),
            Instr("COMPARE_OP", arg=Compare.EQ),
            Instr("POP_JUMP_IF_FALSE", arg=elif_cond),
        ]
    )
    init_block = BasicBlock(
        [
            # foo = 1
            Instr("LOAD_CONST", arg=1),
            Instr("STORE_FAST", arg="foo"),
            # bar = 2
            Instr("LOAD_CONST", arg=2),
            Instr("STORE_FAST", arg="bar"),
        ]
    )

    expected_instructions = []
    expected_instructions.extend(init_block)
    expected_instructions.extend(if_cond)
    expected_instructions.extend(elif_cond)
    expected_instructions.extend(else_block)
    expected_instructions.extend(return_block)

    dynamic_slice = slice_function_at_return(func.__code__)
    assert len(dynamic_slice.sliced_instructions) == len(expected_instructions)
    assert compare(dynamic_slice.sliced_instructions, expected_instructions)


def test_equal_variable_names():
    # Data dependencies across modules (explicit, full cover)
    main_module_block = BasicBlock(
        [
            # class Foo:
            Instr("LOAD_BUILD_CLASS"),
            Instr("LOAD_CONST", arg=dummy_code_object),
            Instr("LOAD_CONST", arg="Foo"),
            Instr("MAKE_FUNCTION", arg=0),
            Instr("LOAD_CONST", arg="Foo"),
            Instr("CALL_FUNCTION", arg=2),
            Instr("STORE_NAME", arg="Foo"),
            # duplicate_var = "foo_dup"
            Instr("LOAD_CONST", arg="foo_dup"),
            Instr("STORE_NAME", arg="duplicate_var"),
            # import tests.slicer.integration.example_modules.equal_variable_names_def
            # Instr("LOAD_CONST", arg=0),
            # Instr("LOAD_CONST", arg=None),
            # Instr("IMPORT_NAME", arg="tests.slicer.integration.example_modules.equal_variable_names_def"),
            # Instr("STORE_NAME", arg="tests"),
            # test = duplicate_var
            Instr("LOAD_NAME", arg="duplicate_var"),
            Instr("STORE_NAME", arg="test"),
            Instr("LOAD_CONST", arg=None),
            Instr("RETURN_VALUE"),
            # result = Foo.test
            Instr("LOAD_NAME", arg="Foo"),
            Instr("LOAD_ATTR", arg="test"),
            Instr("STORE_NAME", arg="result"),
            Instr("LOAD_CONST", arg=None),
            Instr("RETURN_VALUE"),
        ]
    )
    dependency_module_block = BasicBlock(
        [
            # duplicate_var = "bar_dup"
            # Instr("LOAD_CONST", arg="bar_dup"),
            # Instr("STORE_NAME", arg="duplicate_var"),
            # Instr("LOAD_CONST", arg=None),
            # Instr("RETURN_VALUE")
        ]
    )

    expected_instructions = []
    expected_instructions.extend(main_module_block)
    expected_instructions.extend(dependency_module_block)

    module_dependency_file = "equal_variable_names_def.py"
    module_dependency_path = example_modules_path + module_dependency_file
    instrument_module(module_dependency_path)

    module_file = "equal_variable_names_main.py"
    module_path = example_modules_path + module_file
    dynamic_slice = slice_module_at_return(module_path)

    compile_module(module_dependency_path)
    assert len(dynamic_slice.sliced_instructions) == len(expected_instructions)
    assert compare(dynamic_slice.sliced_instructions, expected_instructions)
