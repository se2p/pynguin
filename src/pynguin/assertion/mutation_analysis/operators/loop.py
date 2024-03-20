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

from pynguin.assertion.mutation_analysis.operators import copy_node, MutationOperator


class OneIterationLoop(MutationOperator):
    def one_iteration(self, node):
        node.body.append(ast.Break(lineno=node.body[-1].lineno + 1))
        return node

    @copy_node
    def mutate_For(self, node):
        return self.one_iteration(node)

    @copy_node
    def mutate_While(self, node):
        return self.one_iteration(node)


class ReverseIterationLoop(MutationOperator):
    @copy_node
    def mutate_For(self, node):
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
    def zero_iteration(self, node):
        node.body = [ast.Break(lineno=node.body[0].lineno)]
        return node

    @copy_node
    def mutate_For(self, node):
        return self.zero_iteration(node)

    @copy_node
    def mutate_While(self, node):
        return self.zero_iteration(node)
