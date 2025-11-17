#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides loop operators for mutation analysis.

Based on https://github.com/se2p/mutpy-pynguin/blob/main/mutpy/operators/loop.py
and integrated in Pynguin.
"""

import ast
import typing

from pynguin.assertion.mutation_analysis.operators.base import MutationOperator, copy_node

T = typing.TypeVar("T", ast.For, ast.While)


def one_iteration(node: T) -> T | None:
    """Mutate a loop to have only one iteration.

    Args:
        node: The loop to mutate.

    Returns:
        The mutated loop, or None if the loop should not be mutated.
    """
    if not node.body:
        return None

    mutated_node = copy_node(node)
    mutated_node.body.append(ast.Break(lineno=mutated_node.body[-1].lineno + 1))
    return mutated_node


def zero_iteration(node: T) -> T | None:
    """Mutate a loop to have zero iterations.

    Args:
        node: The loop to mutate.

    Returns:
        The mutated loop, or None if the loop should not be mutated.
    """
    if not node.body:
        return None

    mutated_node = copy_node(node)
    mutated_node.body = [ast.Break(lineno=mutated_node.body[0].lineno)]
    return mutated_node


class OneIterationLoop(MutationOperator):
    """A class that mutates loops to have only one iteration."""

    def mutate_For(self, node: ast.For) -> ast.For | None:  # noqa: N802
        """Mutate a For loop to have only one iteration.

        Args:
            node: The For loop to mutate.

        Returns:
            The mutated loop, or None if the loop should not be mutated.
        """
        return one_iteration(node)

    def mutate_While(self, node: ast.While) -> ast.While | None:  # noqa: N802
        """Mutate a While loop to have only one iteration.

        Args:
            node: The While loop to mutate.

        Returns:
            The mutated loop, or None if the loop should not be mutated.
        """
        return one_iteration(node)


class ReverseIterationLoop(MutationOperator):
    """A class that mutates loops by reversing their iteration."""

    def mutate_For(self, node: ast.For) -> ast.For:  # noqa: N802
        """Mutate a For loop by reversing its iteration.

        Args:
            node: The For loop to mutate.

        Returns:
            The mutated loop.
        """
        mutated_node = copy_node(node)
        old_iter = mutated_node.iter
        mutated_node.iter = ast.Call(  # type: ignore[call-arg]
            func=ast.Name(id=reversed.__name__, ctx=ast.Load()),
            args=[old_iter],
            keywords=[],
            starargs=None,
            kwargs=None,
        )
        return mutated_node


class ZeroIterationLoop(MutationOperator):
    """A class that mutates loops to have zero iterations."""

    def mutate_For(self, node: ast.For) -> ast.For | None:  # noqa: N802
        """Mutate a For loop to have zero iterations.

        Args:
            node: The For loop to mutate.

        Returns:
            The mutated loop, or None if the loop should not be mutated.
        """
        return zero_iteration(node)

    def mutate_While(self, node: ast.While) -> ast.While | None:  # noqa: N802
        """Mutate a While loop to have zero iterations.

        Args:
            node: The While loop to mutate.

        Returns:
            The mutated loop, or None if the loop should not be mutated.
        """
        return zero_iteration(node)
