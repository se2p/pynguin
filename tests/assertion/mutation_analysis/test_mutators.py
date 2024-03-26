#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2023 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import ast
import inspect

from pynguin.assertion.mutation_analysis.mutators import FirstOrderMutator
from pynguin.assertion.mutation_analysis.operators import ArithmeticOperatorReplacement
from pynguin.assertion.mutation_analysis.operators import AssignmentOperatorReplacement
from tests.testutils import assert_mutator_mutation


def test_first_order_mutator_generation():
    assert_mutator_mutation(
        FirstOrderMutator(
            [
                ArithmeticOperatorReplacement,
                AssignmentOperatorReplacement,
            ]
        ),
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
