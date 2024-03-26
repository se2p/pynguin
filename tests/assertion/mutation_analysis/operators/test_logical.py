#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2023 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import ast
import inspect

from pynguin.assertion.mutation_analysis.operators.logical import (
    ConditionalOperatorDeletion,
)
from pynguin.assertion.mutation_analysis.operators.logical import (
    ConditionalOperatorInsertion,
)
from pynguin.assertion.mutation_analysis.operators.logical import (
    LogicalConnectorReplacement,
)
from pynguin.assertion.mutation_analysis.operators.logical import (
    LogicalOperatorDeletion,
)
from pynguin.assertion.mutation_analysis.operators.logical import (
    LogicalOperatorReplacement,
)
from pynguin.assertion.mutation_analysis.operators.logical import (
    RelationalOperatorReplacement,
)
from tests.testutils import assert_mutation


def test_not_operator_negation():
    assert_mutation(
        ConditionalOperatorDeletion,
        inspect.cleandoc(
            """
            x = True
            y = not x
            """
        ),
        {
            inspect.cleandoc(
                """
                x = True
                y = x
                """
            ): ("mutate_UnaryOp", ast.UnaryOp, ast.Name),
        },
    )


def test_not_in_operator_negation():
    assert_mutation(
        ConditionalOperatorDeletion,
        inspect.cleandoc(
            """
            x = 1 not in [1, 2, 3]
            """
        ),
        {
            inspect.cleandoc(
                """
                x = 1 in [1, 2, 3]
                """
            ): ("mutate_NotIn", ast.NotIn, ast.In),
        },
    )


def test_while_condition_negation():
    assert_mutation(
        ConditionalOperatorInsertion,
        inspect.cleandoc(
            """
            x = 1
            while x < 10:
                x += 1
            """
        ),
        {
            inspect.cleandoc(
                """
                x = 1
                while not (x < 10):
                    x += 1
                """
            ): ("mutate_While", ast.While, ast.While),
        },
    )


def test_if_condition_negation():
    assert_mutation(
        ConditionalOperatorInsertion,
        inspect.cleandoc(
            """
            x = 1
            if x < 10:
                x += 1
            """
        ),
        {
            inspect.cleandoc(
                """
                x = 1
                if not (x < 10):
                    x += 1
                """
            ): ("mutate_If", ast.If, ast.If),
        },
    )


def test_if_elif_condition_negation():
    assert_mutation(
        ConditionalOperatorInsertion,
        inspect.cleandoc(
            """
            x = 1
            if x < 10:
                x += 1
            elif x < 20:
                x += 2
            """
        ),
        {
            inspect.cleandoc(
                """
                x = 1
                if not (x < 10):
                    x += 1
                elif x < 20:
                    x += 2
                """
            ): ("mutate_If", ast.If, ast.If),
            inspect.cleandoc(
                """
                x = 1
                if x < 10:
                    x += 1
                elif not (x < 20):
                    x += 2
                """
            ): ("mutate_If", ast.If, ast.If),
        },
    )


def test_in_negation():
    assert_mutation(
        ConditionalOperatorInsertion,
        inspect.cleandoc(
            """
            y = 1 in [1, 2, 3]
            """
        ),
        {
            inspect.cleandoc(
                """
                y = 1 not in [1, 2, 3]
                """
            ): ("mutate_In", ast.In, ast.NotIn),
        },
    )


def test_and_to_or_replacement():
    assert_mutation(
        LogicalConnectorReplacement,
        inspect.cleandoc(
            """
            x = True
            y = False
            z = x and y
            """
        ),
        {
            inspect.cleandoc(
                """
                x = True
                y = False
                z = x or y
                """
            ): ("mutate_And", ast.And, ast.Or),
        },
    )


def test_or_to_and_replacement():
    assert_mutation(
        LogicalConnectorReplacement,
        inspect.cleandoc(
            """
            x = True
            y = False
            z = x or y
            """
        ),
        {
            inspect.cleandoc(
                """
                x = True
                y = False
                z = x and y
                """
            ): ("mutate_Or", ast.Or, ast.And),
        },
    )


def test_logical_operator_deletion():
    assert_mutation(
        LogicalOperatorDeletion,
        inspect.cleandoc(
            """
            x = True
            y = ~x
            """
        ),
        {
            inspect.cleandoc(
                """
                x = True
                y = x
                """
            ): ("mutate_UnaryOp", ast.UnaryOp, ast.Name),
        },
    )


def test_bin_and_to_bin_or_replacement():
    assert_mutation(
        LogicalOperatorReplacement,
        inspect.cleandoc(
            """
            x = 1
            y = 2
            z = x & y
            """
        ),
        {
            inspect.cleandoc(
                """
                x = 1
                y = 2
                z = x | y
                """
            ): ("mutate_BitAnd", ast.BitAnd, ast.BitOr),
        },
    )


def test_bin_or_to_bin_and_replacement():
    assert_mutation(
        LogicalOperatorReplacement,
        inspect.cleandoc(
            """
            x = 1
            y = 2
            z = x | y
            """
        ),
        {
            inspect.cleandoc(
                """
                x = 1
                y = 2
                z = x & y
                """
            ): ("mutate_BitOr", ast.BitOr, ast.BitAnd),
        },
    )


def test_bin_xor_to_bin_and_replacement():
    assert_mutation(
        LogicalOperatorReplacement,
        inspect.cleandoc(
            """
            x = 1
            y = 2
            z = x ^ y
            """
        ),
        {
            inspect.cleandoc(
                """
                x = 1
                y = 2
                z = x & y
                """
            ): ("mutate_BitXor", ast.BitXor, ast.BitAnd),
        },
    )


def test_bin_lshift_to_bin_rshift_replacement():
    assert_mutation(
        LogicalOperatorReplacement,
        inspect.cleandoc(
            """
            x = 1
            y = 2
            z = x << y
            """
        ),
        {
            inspect.cleandoc(
                """
                x = 1
                y = 2
                z = x >> y
                """
            ): ("mutate_LShift", ast.LShift, ast.RShift),
        },
    )


def test_bin_rshift_to_bin_lshift_replacement():
    assert_mutation(
        LogicalOperatorReplacement,
        inspect.cleandoc(
            """
            x = 1
            y = 2
            z = x >> y
            """
        ),
        {
            inspect.cleandoc(
                """
                x = 1
                y = 2
                z = x << y
                """
            ): ("mutate_RShift", ast.RShift, ast.LShift),
        },
    )


def test_lt_replacement():
    assert_mutation(
        RelationalOperatorReplacement,
        inspect.cleandoc(
            """
            x = 1
            y = 2
            z = x < y
            """
        ),
        {
            inspect.cleandoc(
                """
                x = 1
                y = 2
                z = x > y
                """
            ): ("mutate_Lt", ast.Lt, ast.Gt),
            inspect.cleandoc(
                """
                x = 1
                y = 2
                z = x <= y
                """
            ): ("mutate_Lt_to_LtE", ast.Lt, ast.LtE),
        },
    )


def test_gt_replacement():
    assert_mutation(
        RelationalOperatorReplacement,
        inspect.cleandoc(
            """
            x = 1
            y = 2
            z = x > y
            """
        ),
        {
            inspect.cleandoc(
                """
                x = 1
                y = 2
                z = x < y
                """
            ): ("mutate_Gt", ast.Gt, ast.Lt),
            inspect.cleandoc(
                """
                x = 1
                y = 2
                z = x >= y
                """
            ): ("mutate_Gt_to_GtE", ast.Gt, ast.GtE),
        },
    )


def test_lte_replacement():
    assert_mutation(
        RelationalOperatorReplacement,
        inspect.cleandoc(
            """
            x = 1
            y = 2
            z = x <= y
            """
        ),
        {
            inspect.cleandoc(
                """
                x = 1
                y = 2
                z = x >= y
                """
            ): ("mutate_LtE", ast.LtE, ast.GtE),
            inspect.cleandoc(
                """
                x = 1
                y = 2
                z = x < y
                """
            ): ("mutate_LtE_to_Lt", ast.LtE, ast.Lt),
        },
    )


def test_gte_replacement():
    assert_mutation(
        RelationalOperatorReplacement,
        inspect.cleandoc(
            """
            x = 1
            y = 2
            z = x >= y
            """
        ),
        {
            inspect.cleandoc(
                """
                x = 1
                y = 2
                z = x <= y
                """
            ): ("mutate_GtE", ast.GtE, ast.LtE),
            inspect.cleandoc(
                """
                x = 1
                y = 2
                z = x > y
                """
            ): ("mutate_GtE_to_Gt", ast.GtE, ast.Gt),
        },
    )


def test_eq_replacement():
    assert_mutation(
        RelationalOperatorReplacement,
        inspect.cleandoc(
            """
            x = 1
            y = 2
            z = x == y
            """
        ),
        {
            inspect.cleandoc(
                """
                x = 1
                y = 2
                z = x != y
                """
            ): ("mutate_Eq", ast.Eq, ast.NotEq),
        },
    )


def test_not_eq_replacement():
    assert_mutation(
        RelationalOperatorReplacement,
        inspect.cleandoc(
            """
            x = 1
            y = 2
            z = x != y
            """
        ),
        {
            inspect.cleandoc(
                """
                x = 1
                y = 2
                z = x == y
                """
            ): ("mutate_NotEq", ast.NotEq, ast.Eq),
        },
    )
