#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019-2023 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides classes for mutation testing.

Comes from https://github.com/se2p/mutpy-pynguin/blob/main/mutpy/operators/loop.py.
"""

import ast
import typing

from pynguin.assertion.mutation_analysis.operators import copy_node, MutationOperator


T = typing.TypeVar("T", ast.For, ast.While)


def one_iteration(node: T) -> T | None:
    if not node.body:
        return None

    node.body.append(ast.Break(lineno=node.body[-1].lineno + 1))
    return node


def zero_iteration(node: T) -> T | None:
    if not node.body:
        return None

    node.body = [ast.Break(lineno=node.body[0].lineno)]
    return node


class OneIterationLoop(MutationOperator):

    @copy_node
    def mutate_For(self, node: ast.For) -> ast.For | None:
        return one_iteration(node)

    @copy_node
    def mutate_While(self, node: ast.While) -> ast.While | None:
        return one_iteration(node)


class ReverseIterationLoop(MutationOperator):
    @copy_node
    def mutate_For(self, node: ast.For) -> ast.For:
        old_iter = node.iter
        node.iter = ast.Call(
            func=ast.Name(id=reversed.__name__, ctx=ast.Load()),
            args=[old_iter],
            keywords=[],
            starargs=None,
            kwargs=None,
        )
        return node


class ZeroIterationLoop(MutationOperator):

    @copy_node
    def mutate_For(self, node: ast.For) -> ast.For | None:
        return zero_iteration(node)

    @copy_node
    def mutate_While(self, node: ast.While) -> ast.While | None:
        return zero_iteration(node)
