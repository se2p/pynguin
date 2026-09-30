#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2023 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import ast
import inspect

from pynguin.assertion.mutation_analysis.operators.arithmetic import (
    ArithmeticOperatorDeletion,
    ArithmeticOperatorReplacement,
)
from tests.testutils import assert_mutation


def test_usub_deletion():
    assert_mutation(
        ArithmeticOperatorDeletion,
        inspect.cleandoc(
            """
            x = 0
            y = -x
            """
        ),
        {
            inspect.cleandoc(
                """
                x = 0
                y = x
                """
            ): ("mutate_UnaryOp", ast.UnaryOp, ast.Name),
        },
    )


def test_uadd_deletion():
    assert_mutation(
        ArithmeticOperatorDeletion,
        inspect.cleandoc(
            """
            x = 0
            y = +x
            """
        ),
        {
            inspect.cleandoc(
                """
                x = 0
                y = x
                """
            ): ("mutate_UnaryOp", ast.UnaryOp, ast.Name),
        },
    )


def test_add_to_sub_replacement():
    assert_mutation(
        ArithmeticOperatorReplacement,
        inspect.cleandoc(
            """
            x = 0
            y = x + 1
            z = x + 2
            """
        ),
        {
            inspect.cleandoc(
                """
                x = 0
                y = x - 1
                z = x + 2
                """
            ): ("mutate_Add", ast.Add, ast.Sub),
            inspect.cleandoc(
                """
                x = 0
                y = x + 1
                z = x - 2
                """
            ): ("mutate_Add", ast.Add, ast.Sub),
        },
    )


def test_sub_to_add_replacement():
    assert_mutation(
        ArithmeticOperatorReplacement,
        inspect.cleandoc(
            """
            x = 0
            y = x - 1
            z = x - 2
            """
        ),
        {
            inspect.cleandoc(
                """
                x = 0
                y = x + 1
                z = x - 2
                """
            ): ("mutate_Sub", ast.Sub, ast.Add),
            inspect.cleandoc(
                """
                x = 0
                y = x - 1
                z = x + 2
                """
            ): ("mutate_Sub", ast.Sub, ast.Add),
        },
    )


def test_mult_to_div_and_pow_replacement():
    assert_mutation(
        ArithmeticOperatorReplacement,
        inspect.cleandoc(
            """
            x = 0
            y = x * 1
            """
        ),
        {
            inspect.cleandoc(
                """
                x = 0
                y = x / 1
                """
            ): ("mutate_Mult_to_Div", ast.Mult, ast.Div),
            inspect.cleandoc(
                """
                x = 0
                y = x // 1
                """
            ): ("mutate_Mult_to_FloorDiv", ast.Mult, ast.FloorDiv),
            inspect.cleandoc(
                """
                x = 0
                y = x ** 1
                """
            ): ("mutate_Mult_to_Pow", ast.Mult, ast.Pow),
        },
    )


def test_mult_to_pow_skipped_for_self_referential_accumulator_in_loop():
    # Regression test for issue #306: ``x = x * i`` inside a loop must not be
    # mutated to ``x = x ** i``, which grows super-linearly and blocks in C
    # while holding the GIL, so the execution timeout cannot fire.
    assert_mutation(
        ArithmeticOperatorReplacement,
        inspect.cleandoc(
            """
            x = 1
            for i in range(3):
                x = x * i
            """
        ),
        {
            inspect.cleandoc(
                """
                x = 1
                for i in range(3):
                    x = x / i
                """
            ): ("mutate_Mult_to_Div", ast.Mult, ast.Div),
            inspect.cleandoc(
                """
                x = 1
                for i in range(3):
                    x = x // i
                """
            ): ("mutate_Mult_to_FloorDiv", ast.Mult, ast.FloorDiv),
        },
    )


def test_mult_to_pow_kept_for_self_reference_without_loop():
    # A self-referential multiplication that is not in a loop runs once and is
    # bounded, so the ``Mult -> Pow`` mutant is still generated.
    assert_mutation(
        ArithmeticOperatorReplacement,
        inspect.cleandoc(
            """
            x = 1
            x = x * 2
            """
        ),
        {
            inspect.cleandoc(
                """
                x = 1
                x = x / 2
                """
            ): ("mutate_Mult_to_Div", ast.Mult, ast.Div),
            inspect.cleandoc(
                """
                x = 1
                x = x // 2
                """
            ): ("mutate_Mult_to_FloorDiv", ast.Mult, ast.FloorDiv),
            inspect.cleandoc(
                """
                x = 1
                x = x ** 2
                """
            ): ("mutate_Mult_to_Pow", ast.Mult, ast.Pow),
        },
    )


def test_mult_to_pow_kept_in_loop_without_self_reference():
    # A multiplication in a loop that does not feed back into its own operands
    # does not blow up, so the ``Mult -> Pow`` mutant is still generated.
    assert_mutation(
        ArithmeticOperatorReplacement,
        inspect.cleandoc(
            """
            y = 1
            for i in range(3):
                y = i * 2
            """
        ),
        {
            inspect.cleandoc(
                """
                y = 1
                for i in range(3):
                    y = i / 2
                """
            ): ("mutate_Mult_to_Div", ast.Mult, ast.Div),
            inspect.cleandoc(
                """
                y = 1
                for i in range(3):
                    y = i // 2
                """
            ): ("mutate_Mult_to_FloorDiv", ast.Mult, ast.FloorDiv),
            inspect.cleandoc(
                """
                y = 1
                for i in range(3):
                    y = i ** 2
                """
            ): ("mutate_Mult_to_Pow", ast.Mult, ast.Pow),
        },
    )


def test_div_to_mult_and_floordiv_replacement():
    assert_mutation(
        ArithmeticOperatorReplacement,
        inspect.cleandoc(
            """
            x = 0
            y = x / 1
            """
        ),
        {
            inspect.cleandoc(
                """
                x = 0
                y = x * 1
                """
            ): ("mutate_Div_to_Mult", ast.Div, ast.Mult),
            inspect.cleandoc(
                """
                x = 0
                y = x // 1
                """
            ): ("mutate_Div_to_FloorDiv", ast.Div, ast.FloorDiv),
        },
    )


def test_floor_div_to_mult_and_div_replacement():
    assert_mutation(
        ArithmeticOperatorReplacement,
        inspect.cleandoc(
            """
            x = 0
            y = x // 1
            """
        ),
        {
            inspect.cleandoc(
                """
                x = 0
                y = x * 1
                """
            ): ("mutate_FloorDiv_to_Mult", ast.FloorDiv, ast.Mult),
            inspect.cleandoc(
                """
                x = 0
                y = x / 1
                """
            ): ("mutate_FloorDiv_to_Div", ast.FloorDiv, ast.Div),
        },
    )


def test_mod_to_mult_replacement():
    assert_mutation(
        ArithmeticOperatorReplacement,
        inspect.cleandoc(
            """
            x = 0
            y = x % 1
            """
        ),
        {
            inspect.cleandoc(
                """
                x = 0
                y = x * 1
                """
            ): ("mutate_Mod", ast.Mod, ast.Mult),
        },
    )


def test_pow_to_mult_replacement():
    assert_mutation(
        ArithmeticOperatorReplacement,
        inspect.cleandoc(
            """
            x = 0
            y = x ** 1
            """
        ),
        {
            inspect.cleandoc(
                """
                x = 0
                y = x * 1
                """
            ): ("mutate_Pow", ast.Pow, ast.Mult),
        },
    )


def test_augmented_assign_ignore():
    assert_mutation(
        ArithmeticOperatorReplacement,
        inspect.cleandoc(
            """
            x = 0
            x += 1
            """
        ),
        {},
    )


def test_usub_replacement():
    assert_mutation(
        ArithmeticOperatorReplacement,
        inspect.cleandoc(
            """
            x = 0
            y = -x
            """
        ),
        {
            inspect.cleandoc(
                """
                x = 0
                y = +x
                """
            ): ("mutate_USub", ast.USub, ast.UAdd),
        },
    )


def test_uadd_replacement():
    assert_mutation(
        ArithmeticOperatorReplacement,
        inspect.cleandoc(
            """
            x = 0
            y = +x
            """
        ),
        {
            inspect.cleandoc(
                """
                x = 0
                y = -x
                """
            ): ("mutate_UAdd", ast.UAdd, ast.USub),
        },
    )
