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
    ExceptionSwallowing,
    ExceptionTypeReplacement,
)
from tests.testutils import assert_mutation


def test_exception_type_replacement_call():
    assert_mutation(
        ExceptionTypeReplacement,
        inspect.cleandoc(
            """
            def foo():
                raise ValueError('message')
            """
        ),
        {
            inspect.cleandoc(
                """
                def foo():
                    raise RuntimeError('message')
                """
            ): ("mutate_Raise", ast.Raise, ast.Raise),
        },
    )


def test_exception_type_replacement_default_to_fallback():
    assert_mutation(
        ExceptionTypeReplacement,
        inspect.cleandoc(
            """
            def foo():
                raise RuntimeError('message')
            """
        ),
        {
            inspect.cleandoc(
                """
                def foo():
                    raise ValueError('message')
                """
            ): ("mutate_Raise", ast.Raise, ast.Raise),
        },
    )


def test_exception_type_replacement_name():
    assert_mutation(
        ExceptionTypeReplacement,
        inspect.cleandoc(
            """
            def foo(error):
                raise error
            """
        ),
        {
            inspect.cleandoc(
                """
                def foo(error):
                    raise RuntimeError
                """
            ): ("mutate_Raise", ast.Raise, ast.Raise),
        },
    )


def test_exception_type_replacement_bare_raise_not_mutated():
    assert_mutation(
        ExceptionTypeReplacement,
        inspect.cleandoc(
            """
            def foo():
                try:
                    pass
                except ValueError:
                    raise
            """
        ),
        {},
    )


def test_exception_type_replacement_attribute_not_mutated():
    assert_mutation(
        ExceptionTypeReplacement,
        inspect.cleandoc(
            """
            import builtins

            def foo():
                raise builtins.ValueError('message')
            """
        ),
        {},
    )


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
