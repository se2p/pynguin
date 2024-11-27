#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2023 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import ast
import inspect

from pynguin.assertion.mutation_analysis.operators.misc import (
    AssignmentOperatorReplacement,
)
from pynguin.assertion.mutation_analysis.operators.misc import BreakContinueReplacement
from pynguin.assertion.mutation_analysis.operators.misc import ConstantReplacement
from pynguin.assertion.mutation_analysis.operators.misc import SliceIndexRemove
from tests.testutils import assert_mutation


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
