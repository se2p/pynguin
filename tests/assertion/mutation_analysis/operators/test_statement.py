#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import ast
import inspect

from pynguin.assertion.mutation_analysis.operators.statement import (
    AssertionRemoval,
    ReturnValueReplacement,
)
from tests.testutils import assert_mutation


def test_return_int_replaced_with_none():
    assert_mutation(
        ReturnValueReplacement,
        inspect.cleandoc(
            """
            def foo():
                return 42
            """
        ),
        {
            inspect.cleandoc(
                """
                def foo():
                    return None
                """
            ): ("mutate_Return", ast.Return, ast.Return),
        },
    )


def test_return_string_replaced_with_none():
    assert_mutation(
        ReturnValueReplacement,
        inspect.cleandoc(
            """
            def foo():
                return "hello"
            """
        ),
        {
            inspect.cleandoc(
                """
                def foo():
                    return None
                """
            ): ("mutate_Return", ast.Return, ast.Return),
        },
    )


def test_return_expr_replaced_with_none():
    assert_mutation(
        ReturnValueReplacement,
        inspect.cleandoc(
            """
            def foo(x):
                return x + 1
            """
        ),
        {
            inspect.cleandoc(
                """
                def foo(x):
                    return None
                """
            ): ("mutate_Return", ast.Return, ast.Return),
        },
    )


def test_bare_return_no_mutation():
    assert_mutation(
        ReturnValueReplacement,
        inspect.cleandoc(
            """
            def foo():
                return
            """
        ),
        {},
    )


def test_return_none_no_mutation():
    assert_mutation(
        ReturnValueReplacement,
        inspect.cleandoc(
            """
            def foo():
                return None
            """
        ),
        {},
    )


def test_assert_replaced_with_pass():
    assert_mutation(
        AssertionRemoval,
        inspect.cleandoc(
            """
            x = 1
            assert x == 1
            """
        ),
        {
            inspect.cleandoc(
                """
                x = 1
                pass
                """
            ): ("mutate_Assert", ast.Assert, ast.Pass),
        },
    )


def test_assert_with_message_replaced_with_pass():
    assert_mutation(
        AssertionRemoval,
        inspect.cleandoc(
            """
            x = 1
            assert x > 0, "msg"
            """
        ),
        {
            inspect.cleandoc(
                """
                x = 1
                pass
                """
            ): ("mutate_Assert", ast.Assert, ast.Pass),
        },
    )
