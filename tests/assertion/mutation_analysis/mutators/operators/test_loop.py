#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2023 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import ast
import inspect

from pynguin.assertion.mutation_analysis.operators.loop import OneIterationLoop
from pynguin.assertion.mutation_analysis.operators.loop import ReverseIterationLoop
from pynguin.assertion.mutation_analysis.operators.loop import ZeroIterationLoop
from tests.testutils import assert_mutation


def test_one_iteration_for_loop_break():
    assert_mutation(
        OneIterationLoop,
        inspect.cleandoc(
            """
            for x in range(10):
                pass
            """
        ),
        {
            inspect.cleandoc(
                """
                for x in range(10):
                    pass
                    break
                """
            ): ("mutate_For", ast.For, ast.For),
        },
    )


def test_one_iteration_while_loop_break():
    assert_mutation(
        OneIterationLoop,
        inspect.cleandoc(
            """
            i = 0
            while i < 10:
                i += 1
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
            ): ("mutate_While", ast.While, ast.While),
        },
    )


def test_one_iteration_multiple_loops_break():
    assert_mutation(
        OneIterationLoop,
        inspect.cleandoc(
            """
            for x in range(10):
                pass
            i = 0
            while i < 10:
                i += 1
            """
        ),
        {
            inspect.cleandoc(
                """
                for x in range(10):
                    pass
                    break
                i = 0
                while i < 10:
                    i += 1
                """
            ): ("mutate_For", ast.For, ast.For),
            inspect.cleandoc(
                """
                for x in range(10):
                    pass
                i = 0
                while i < 10:
                    i += 1
                    break
                """
            ): ("mutate_While", ast.While, ast.While),
        },
    )


def test_zero_iteration_for_loop_break():
    assert_mutation(
        ZeroIterationLoop,
        inspect.cleandoc(
            """
            for x in range(10):
                pass
            """
        ),
        {
            inspect.cleandoc(
                """
                for x in range(10):
                    break
                """
            ): ("mutate_For", ast.For, ast.For),
        },
    )


def test_zero_iteration_while_loop_break():
    assert_mutation(
        ZeroIterationLoop,
        inspect.cleandoc(
            """
            i = 0
            while i < 10:
                i += 1
            """
        ),
        {
            inspect.cleandoc(
                """
                i = 0
                while i < 10:
                    break
                """
            ): ("mutate_While", ast.While, ast.While),
        },
    )


def test_zero_iteration_for_loop_multiple_statements_break():
    assert_mutation(
        ZeroIterationLoop,
        inspect.cleandoc(
            """
            for x in range(10):
                pass
                pass
            """
        ),
        {
            inspect.cleandoc(
                """
                for x in range(10):
                    break
                """
            ): ("mutate_For", ast.For, ast.For),
        },
    )


def test_reverse_iteration_for_loop():
    assert_mutation(
        ReverseIterationLoop,
        inspect.cleandoc(
            """
            for x in range(10):
                pass
            """
        ),
        {
            inspect.cleandoc(
                """
                for x in reversed(range(10)):
                    pass
                """
            ): ("mutate_For", ast.For, ast.For),
        },
    )
