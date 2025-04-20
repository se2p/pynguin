#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import ast
import inspect

from pynguin.assertion.mutation_analysis.mutators import FirstOrderMutator
from pynguin.assertion.mutation_analysis.mutators import HighOrderMutator
from pynguin.assertion.mutation_analysis.operators import ArithmeticOperatorDeletion
from pynguin.assertion.mutation_analysis.operators import ArithmeticOperatorReplacement
from pynguin.assertion.mutation_analysis.operators import AssignmentOperatorReplacement
from pynguin.assertion.mutation_analysis.operators import ConstantReplacement
from tests.testutils import assert_mutator_mutation


def test_first_order_mutator_generation():
    assert_mutator_mutation(
        FirstOrderMutator([
            ArithmeticOperatorReplacement,
            AssignmentOperatorReplacement,
        ]),
        inspect.cleandoc(
            """
            x = 1
            y = 2
            z = 0
            z += x + y
            """
        ),
        {
            inspect.cleandoc(
                """
                x = 1
                y = 2
                z = 0
                z -= x + y
                """
            ): {(AssignmentOperatorReplacement, "mutate_Add", ast.Add, ast.Sub)},
            inspect.cleandoc(
                """
                x = 1
                y = 2
                z = 0
                z += x - y
                """
            ): {(ArithmeticOperatorReplacement, "mutate_Add", ast.Add, ast.Sub)},
        },
    )


def test_high_order_mutator_generation():
    assert_mutator_mutation(
        HighOrderMutator([
            ArithmeticOperatorReplacement,
            AssignmentOperatorReplacement,
        ]),
        inspect.cleandoc(
            """
            x = 1
            y = 2
            z = 0
            z += x + y
            """
        ),
        {
            inspect.cleandoc(
                """
                x = 1
                y = 2
                z = 0
                z -= x - y
                """
            ): {
                (AssignmentOperatorReplacement, "mutate_Add", ast.Add, ast.Sub),
                (ArithmeticOperatorReplacement, "mutate_Add", ast.Add, ast.Sub),
            },
        },
    )


def test_high_order_mutator_generation_with_same_node():
    assert_mutator_mutation(
        HighOrderMutator([
            ArithmeticOperatorDeletion,
            ArithmeticOperatorReplacement,
        ]),
        inspect.cleandoc(
            """
            x = 1
            y = -x
            """
        ),
        {
            inspect.cleandoc(
                """
                x = 1
                y = x
                """
            ): {
                (ArithmeticOperatorDeletion, "mutate_UnaryOp", ast.UnaryOp, ast.Name),
            },
            inspect.cleandoc(
                """
                x = 1
                y = +x
                """
            ): {
                (ArithmeticOperatorReplacement, "mutate_USub", ast.USub, ast.UAdd),
            },
        },
    )


def test_high_order_mutator_generation_with_multiple_visitors():
    assert_mutator_mutation(
        HighOrderMutator([ConstantReplacement]),
        inspect.cleandoc(
            """
            x = 'test'
            """
        ),
        {
            inspect.cleandoc(
                f"""
                x = '{ConstantReplacement.FIRST_CONST_STRING}'
                """
            ): {
                (
                    ConstantReplacement,
                    "mutate_Constant_str",
                    ast.Constant,
                    ast.Constant,
                ),
            },
            inspect.cleandoc(
                """
                x = ''
                """
            ): {
                (
                    ConstantReplacement,
                    "mutate_Constant_str_empty",
                    ast.Constant,
                    ast.Constant,
                ),
            },
        },
    )
