#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import ast
import inspect
import sys

import pytest

from pynguin.assertion.mutation_analysis.operators.statement import (
    AssertionRemoval,
    MatchCaseDeletion,
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


@pytest.mark.skipif(sys.version_info < (3, 10), reason="match statement requires Python 3.10+")
def test_match_case_remove_first_and_last():
    assert_mutation(
        MatchCaseDeletion,
        inspect.cleandoc(
            """
            x = 0
            match x:
                case 1:
                    pass
                case 2:
                    pass
                case _:
                    pass
            """
        ),
        {
            inspect.cleandoc(
                """
                x = 0
                match x:
                    case 2:
                        pass
                    case _:
                        pass
                """
            ): ("mutate_Match_remove_first", ast.Match, ast.Match),
            inspect.cleandoc(
                """
                x = 0
                match x:
                    case 1:
                        pass
                    case 2:
                        pass
                """
            ): ("mutate_Match_remove_last", ast.Match, ast.Match),
        },
    )


@pytest.mark.skipif(sys.version_info < (3, 10), reason="match statement requires Python 3.10+")
def test_match_single_case_no_mutation():
    assert_mutation(
        MatchCaseDeletion,
        inspect.cleandoc(
            """
            x = 0
            match x:
                case _:
                    pass
            """
        ),
        {},
    )
