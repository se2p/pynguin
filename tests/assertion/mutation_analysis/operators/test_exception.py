#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2023 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import ast
import inspect

from pynguin.assertion.mutation_analysis.operators.exception import (
    ExceptionHandlerDeletion,
)
from pynguin.assertion.mutation_analysis.operators.exception import ExceptionSwallowing
from tests.testutils import assert_mutation


def test_exception_handler_deletion():
    assert_mutation(
        ExceptionHandlerDeletion,
        inspect.cleandoc(
            """
            try:
                pass
            except ValueError:
                pass
            """
        ),
        {
            inspect.cleandoc(
                """
                try:
                    pass
                except ValueError:
                    raise
                """
            ): ("mutate_ExceptHandler", ast.ExceptHandler, ast.ExceptHandler),
        },
    )


def test_two_exception_handler_deletion():
    assert_mutation(
        ExceptionHandlerDeletion,
        inspect.cleandoc(
            """
            try:
                pass
            except ValueError:
                pass
            except ZeroDivisionError:
                pass
            """
        ),
        {
            inspect.cleandoc(
                """
                try:
                    pass
                except ValueError:
                    raise
                except ZeroDivisionError:
                    pass
                """
            ): ("mutate_ExceptHandler", ast.ExceptHandler, ast.ExceptHandler),
            inspect.cleandoc(
                """
                try:
                    pass
                except ValueError:
                    pass
                except ZeroDivisionError:
                    raise
                """
            ): ("mutate_ExceptHandler", ast.ExceptHandler, ast.ExceptHandler),
        },
    )


def test_raise_no_deletion():
    assert_mutation(
        ExceptionHandlerDeletion,
        inspect.cleandoc(
            """
            try:
                pass
            except ValueError:
                raise
            """
        ),
        {},
    )


def test_exception_swallowing():
    assert_mutation(
        ExceptionSwallowing,
        inspect.cleandoc(
            """
            try:
                pass
            except ValueError:
                raise
            """
        ),
        {
            inspect.cleandoc(
                """
                try:
                    pass
                except ValueError:
                    pass
                """
            ): ("mutate_ExceptHandler", ast.ExceptHandler, ast.ExceptHandler),
        },
    )


def test_exception_no_swallowing_when_pass():
    assert_mutation(
        ExceptionSwallowing,
        inspect.cleandoc(
            """
            try:
                pass
            except ValueError:
                pass
            """
        ),
        {},
    )
