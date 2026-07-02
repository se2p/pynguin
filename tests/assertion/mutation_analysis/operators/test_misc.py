#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2023 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import ast
import inspect

import pytest

from pynguin.assertion.mutation_analysis.operators.misc import (
    AssignmentOperatorReplacement,
    AssignmentValueReplacement,
    BooleanLiteralReplacement,
    BreakContinueReplacement,
    ConstantReplacement,
    FStringReplacement,
    LambdaReplacement,
    SliceIndexRemove,
    is_docstring,
)
from tests.testutils import assert_mutation


def _attach_parents(node: ast.AST):
    for child in ast.iter_child_nodes(node):
        child.parent = node
        _attach_parents(child)


@pytest.mark.parametrize(
    "code,expected",
    [
        ("def foo():\n    '''Docstring'''\n    pass", True),
        ("def foo():\n    pass", False),
        ('class Bar:\n    """Docstring"""\n    pass', True),
        ("class Bar:\n    pass", False),
        ("'''Module docstring'''\nimport sys", True),
        ("import sys", False),
    ],
)
def test_is_docstring_combined(code, expected):
    tree = ast.parse(code)
    _attach_parents(tree)

    found = False
    for node in ast.walk(tree):
        if node and hasattr(node, "value") and is_docstring(node.value):
            found = True

    assert found == expected


def test_add_to_sub_replacement():
    assert_mutation(
        AssignmentOperatorReplacement,
        inspect.cleandoc(
            """
            x = 0
            x += 1
            """
        ),
        {
            inspect.cleandoc(
                """
                x = 0
                x -= 1
                """
            ): ("mutate_Add", ast.Add, ast.Sub),
        },
    )


def test_sub_to_add_replacement():
    assert_mutation(
        AssignmentOperatorReplacement,
        inspect.cleandoc(
            """
            x = 0
            x -= 1
            """
        ),
        {
            inspect.cleandoc(
                """
                x = 0
                x += 1
                """
            ): ("mutate_Sub", ast.Sub, ast.Add),
        },
    )


def test_normal_use_ignore():
    assert_mutation(
        AssignmentOperatorReplacement,
        inspect.cleandoc(
            """
            x = 0
            x = x + 1
            """
        ),
        {},
    )


def test_break_to_continue_replacement():
    assert_mutation(
        BreakContinueReplacement,
        inspect.cleandoc(
            """
            i = 0
            while i < 10:
                i += 1
                break
            """
        ),
        {
            inspect.cleandoc(
                """
                i = 0
                while i < 10:
                    i += 1
                    continue
                """
            ): ("mutate_Break", ast.Break, ast.Continue),
            inspect.cleandoc(
                """
                i = 0
                while i < 10:
                    i += 1
                    return
                """
            ): ("mutate_Break_to_return", ast.Break, ast.Return),
        },
    )


def test_continue_to_break_replacement():
    assert_mutation(
        BreakContinueReplacement,
        inspect.cleandoc(
            """
            i = 0
            while i < 10:
                i += 1
                continue
            """
        ),
        {
            inspect.cleandoc(
                """
                i = 0
                while i < 10:
                    i += 1
                    break
                """
            ): ("mutate_Continue", ast.Continue, ast.Break),
        },
    )


def test_numbers_increase():
    assert_mutation(
        ConstantReplacement,
        inspect.cleandoc(
            """
            x = 1 - 2 + 99
            """
        ),
        {
            inspect.cleandoc(
                """
                x = 2 - 2 + 99
                """
            ): ("mutate_Constant_num", ast.Constant, ast.Constant),
            inspect.cleandoc(
                """
                x = 1 - 3 + 99
                """
            ): ("mutate_Constant_num", ast.Constant, ast.Constant),
            inspect.cleandoc(
                """
                x = 1 - 2 + 100
                """
            ): ("mutate_Constant_num", ast.Constant, ast.Constant),
            inspect.cleandoc(
                """
                x = 0 - 2 + 99
                """
            ): ("mutate_Constant_num_zero", ast.Constant, ast.Constant),
            inspect.cleandoc(
                """
                x = 1 - 0 + 99
                """
            ): ("mutate_Constant_num_zero", ast.Constant, ast.Constant),
            inspect.cleandoc(
                """
                x = 1 - 2 + 0
                """
            ): ("mutate_Constant_num_zero", ast.Constant, ast.Constant),
            inspect.cleandoc(
                """
                x = -1 - 2 + 99
                """
            ): ("mutate_Constant_num_neg", ast.Constant, ast.Constant),
            inspect.cleandoc(
                """
                x = 1 - -2 + 99
                """
            ): ("mutate_Constant_num_neg", ast.Constant, ast.Constant),
            inspect.cleandoc(
                """
                x = 1 - 2 + -99
                """
            ): ("mutate_Constant_num_neg", ast.Constant, ast.Constant),
            inspect.cleandoc(
                """
                x = 1 - 1 + 99
                """
            ): ("mutate_Constant_num_decrement", ast.Constant, ast.Constant),
            inspect.cleandoc(
                """
                x = 1 - 2 + 98
                """
            ): ("mutate_Constant_num_decrement", ast.Constant, ast.Constant),
        },
    )


def test_string_replacement():
    assert_mutation(
        ConstantReplacement,
        inspect.cleandoc(
            """
            x = 'x'
            y = '' + 'y'
            """
        ),
        {
            inspect.cleandoc(
                f"""
                x = '{ConstantReplacement.FIRST_CONST_STRING}'
                y = '' + 'y'
                """
            ): ("mutate_Constant_str", ast.Constant, ast.Constant),
            inspect.cleandoc(
                f"""
                x = 'x'
                y = '{ConstantReplacement.FIRST_CONST_STRING}' + 'y'
                """
            ): ("mutate_Constant_str", ast.Constant, ast.Constant),
            inspect.cleandoc(
                f"""
                x = 'x'
                y = '' + '{ConstantReplacement.FIRST_CONST_STRING}'
                """
            ): ("mutate_Constant_str", ast.Constant, ast.Constant),
            inspect.cleandoc(
                """
                x = ''
                y = '' + 'y'
                """
            ): ("mutate_Constant_str_empty", ast.Constant, ast.Constant),
            inspect.cleandoc(
                """
                x = 'x'
                y = '' + ''
                """
            ): ("mutate_Constant_str_empty", ast.Constant, ast.Constant),
            inspect.cleandoc(
                """
                x = 'x'
                y = '' + ''
                """
            ): ("mutate_Constant_str_empty", ast.Constant, ast.Constant),
        },
    )


def test_first_constant_string_replacement():
    assert_mutation(
        ConstantReplacement,
        inspect.cleandoc(
            f"""
            x = '{ConstantReplacement.FIRST_CONST_STRING}'
            """
        ),
        {
            inspect.cleandoc(
                f"""
                x = '{ConstantReplacement.SECOND_CONST_STRING}'
                """
            ): ("mutate_Constant_str", ast.Constant, ast.Constant),
            inspect.cleandoc(
                """
                x = ''
                """
            ): ("mutate_Constant_str_empty", ast.Constant, ast.Constant),
        },
    )


def test_docstring_ignore():
    assert_mutation(
        ConstantReplacement,
        inspect.cleandoc(
            """
            def foo():
                '''Docstring'''
                pass
            """
        ),
        {},
    )


def test_slice_index_replacement():
    assert_mutation(
        SliceIndexRemove,
        inspect.cleandoc(
            """
            x = [1, 2, 3]
            y = x[1:2]
            """
        ),
        {
            inspect.cleandoc(
                """
                x = [1, 2, 3]
                y = x[1:]
                """
            ): ("mutate_Slice_remove_upper", ast.Slice, ast.Slice),
            inspect.cleandoc(
                """
                x = [1, 2, 3]
                y = x[:2]
                """
            ): ("mutate_Slice_remove_lower", ast.Slice, ast.Slice),
        },
    )


def test_constant_replacement_num_zero():
    assert_mutation(
        ConstantReplacement,
        inspect.cleandoc(
            """
            x = 5
            """
        ),
        {
            inspect.cleandoc(
                """
                x = 6
                """
            ): ("mutate_Constant_num", ast.Constant, ast.Constant),
            inspect.cleandoc(
                """
                x = 0
                """
            ): ("mutate_Constant_num_zero", ast.Constant, ast.Constant),
            inspect.cleandoc(
                """
                x = -5
                """
            ): ("mutate_Constant_num_neg", ast.Constant, ast.Constant),
            inspect.cleandoc(
                """
                x = 4
                """
            ): ("mutate_Constant_num_decrement", ast.Constant, ast.Constant),
        },
    )


def test_constant_replacement_num_neg():
    assert_mutation(
        ConstantReplacement,
        inspect.cleandoc(
            """
            x = 3
            """
        ),
        {
            inspect.cleandoc(
                """
                x = 4
                """
            ): ("mutate_Constant_num", ast.Constant, ast.Constant),
            inspect.cleandoc(
                """
                x = 0
                """
            ): ("mutate_Constant_num_zero", ast.Constant, ast.Constant),
            inspect.cleandoc(
                """
                x = -3
                """
            ): ("mutate_Constant_num_neg", ast.Constant, ast.Constant),
            inspect.cleandoc(
                """
                x = 2
                """
            ): ("mutate_Constant_num_decrement", ast.Constant, ast.Constant),
        },
    )


def test_constant_replacement_num_zero_skip():
    assert_mutation(
        ConstantReplacement,
        inspect.cleandoc(
            """
            x = 0
            """
        ),
        {
            inspect.cleandoc(
                """
                x = 1
                """
            ): ("mutate_Constant_num", ast.Constant, ast.Constant),
            inspect.cleandoc(
                """
                x = -1
                """
            ): ("mutate_Constant_num_decrement", ast.Constant, ast.Constant),
        },
    )


def test_constant_replacement_num_decrement_skip_one():
    assert_mutation(
        ConstantReplacement,
        inspect.cleandoc(
            """
            x = 1
            """
        ),
        {
            inspect.cleandoc(
                """
                x = 2
                """
            ): ("mutate_Constant_num", ast.Constant, ast.Constant),
            inspect.cleandoc(
                """
                x = 0
                """
            ): ("mutate_Constant_num_zero", ast.Constant, ast.Constant),
            inspect.cleandoc(
                """
                x = -1
                """
            ): ("mutate_Constant_num_neg", ast.Constant, ast.Constant),
        },
    )


def test_boolean_true_to_false():
    assert_mutation(
        BooleanLiteralReplacement,
        inspect.cleandoc(
            """
            x = True
            """
        ),
        {
            inspect.cleandoc(
                """
                x = False
                """
            ): ("mutate_Constant_bool", ast.Constant, ast.Constant),
        },
    )


def test_boolean_false_to_true():
    assert_mutation(
        BooleanLiteralReplacement,
        inspect.cleandoc(
            """
            x = False
            """
        ),
        {
            inspect.cleandoc(
                """
                x = True
                """
            ): ("mutate_Constant_bool", ast.Constant, ast.Constant),
        },
    )


def test_break_to_return_replacement():
    assert_mutation(
        BreakContinueReplacement,
        inspect.cleandoc(
            """
            for x in [1, 2, 3]:
                break
            """
        ),
        {
            inspect.cleandoc(
                """
                for x in [1, 2, 3]:
                    continue
                """
            ): ("mutate_Break", ast.Break, ast.Continue),
            inspect.cleandoc(
                """
                for x in [1, 2, 3]:
                    return
                """
            ): ("mutate_Break_to_return", ast.Break, ast.Return),
        },
    )


def test_lambda_body_replaced_with_none():
    assert_mutation(
        LambdaReplacement,
        inspect.cleandoc(
            """
            f = lambda x: x + 1
            """
        ),
        {
            inspect.cleandoc(
                """
                f = lambda x: None
                """
            ): ("mutate_Lambda", ast.Lambda, ast.Lambda),
        },
    )


def test_lambda_already_none_skipped():
    assert_mutation(
        LambdaReplacement,
        inspect.cleandoc(
            """
            f = lambda x: None
            """
        ),
        {},
    )


def test_assignment_value_replaced_with_none():
    assert_mutation(
        AssignmentValueReplacement,
        inspect.cleandoc(
            """
            x = 42
            """
        ),
        {
            inspect.cleandoc(
                """
                x = None
                """
            ): ("mutate_Assign", ast.Assign, ast.Assign),
        },
    )


def test_assignment_already_none_skipped():
    assert_mutation(
        AssignmentValueReplacement,
        inspect.cleandoc(
            """
            x = None
            """
        ),
        {},
    )


def test_fstring_replaced_with_constant():
    assert_mutation(
        FStringReplacement,
        inspect.cleandoc(
            """
            name = 'world'
            x = f'hello {name}'
            """
        ),
        {
            inspect.cleandoc(
                f"""
                name = 'world'
                x = '{FStringReplacement.REPLACEMENT_STRING}'
                """
            ): ("mutate_JoinedStr", ast.JoinedStr, ast.Constant),
        },
    )


def test_fstring_without_interpolation_replaced_with_constant():
    assert_mutation(
        FStringReplacement,
        inspect.cleandoc(
            """
            x = f'hello'
            """
        ),
        {
            inspect.cleandoc(
                f"""
                x = '{FStringReplacement.REPLACEMENT_STRING}'
                """
            ): ("mutate_JoinedStr", ast.JoinedStr, ast.Constant),
        },
    )


def test_fstring_format_spec_not_replaced():
    assert_mutation(
        FStringReplacement,
        inspect.cleandoc(
            """
            value = 3.14159
            width = 10
            x = f'{value:{width}}'
            """
        ),
        {
            inspect.cleandoc(
                f"""
                value = 3.14159
                width = 10
                x = '{FStringReplacement.REPLACEMENT_STRING}'
                """
            ): ("mutate_JoinedStr", ast.JoinedStr, ast.Constant),
        },
    )


def test_fstring_in_raise_message_not_replaced():
    assert_mutation(
        FStringReplacement,
        inspect.cleandoc(
            """
            def foo(x):
                raise ValueError(f'bad value {x}')
            """
        ),
        {},
    )


def test_fstring_in_print_call_not_replaced():
    assert_mutation(
        FStringReplacement,
        inspect.cleandoc(
            """
            def foo(x):
                print(f'value is {x}')
            """
        ),
        {},
    )


def test_fstring_in_logging_call_not_replaced():
    assert_mutation(
        FStringReplacement,
        inspect.cleandoc(
            """
            def foo(logger, x):
                logger.warning(f'value is {x}')
            """
        ),
        {},
    )


def test_string_in_raise_message_not_replaced():
    assert_mutation(
        ConstantReplacement,
        inspect.cleandoc(
            """
            def foo():
                raise ValueError('bad value')
            """
        ),
        {},
    )


def test_string_in_logging_call_not_replaced():
    assert_mutation(
        ConstantReplacement,
        inspect.cleandoc(
            """
            def foo(logger):
                logger.info('message')
            """
        ),
        {},
    )
