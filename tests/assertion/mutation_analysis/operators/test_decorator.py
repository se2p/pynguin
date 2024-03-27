#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2023 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import ast
import inspect

from pynguin.assertion.mutation_analysis.operators.decorator import DecoratorDeletion
from tests.testutils import assert_mutation


def test_single_decorator_deletion():
    assert_mutation(
        DecoratorDeletion,
        inspect.cleandoc(
            """
            import atexit

            @atexit.register
            def foo():
                pass
            """
        ),
        {
            inspect.cleandoc(
                """
                import atexit

                def foo():
                    pass
                """
            ): ("mutate_FunctionDef", ast.FunctionDef, ast.FunctionDef),
        },
    )


def test_multiple_decorators_deletion():
    assert_mutation(
        DecoratorDeletion,
        inspect.cleandoc(
            """
            from abc import ABC, abstractmethod

            class Foo(ABC):
                @classmethod
                @abstractmethod
                def bar():
                    pass
            """
        ),
        {
            inspect.cleandoc(
                """
                from abc import ABC, abstractmethod

                class Foo(ABC):
                    def bar():
                        pass
                """
            ): ("mutate_FunctionDef", ast.FunctionDef, ast.FunctionDef),
        },
    )


def test_decorator_with_arguments_deletion():
    assert_mutation(
        DecoratorDeletion,
        inspect.cleandoc(
            """
            from functools import lru_cache

            @lru_cache(maxsize=128)
            def foo(x: int) -> int:
                return x
            """
        ),
        {
            inspect.cleandoc(
                """
                from functools import lru_cache

                def foo(x: int) -> int:
                    return x
                """
            ): ("mutate_FunctionDef", ast.FunctionDef, ast.FunctionDef),
        },
    )
