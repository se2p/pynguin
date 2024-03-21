#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019-2023 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides classes for mutation testing.

Comes from https://github.com/se2p/mutpy-pynguin/blob/main/mutpy/operators/decorator.py.
"""

import ast

from pynguin.assertion.mutation_analysis.operators.base import MutationOperator, copy_node, MutationResign


class DecoratorDeletion(MutationOperator):
    @copy_node
    def mutate_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        if node.decorator_list:
            node.decorator_list = []
            return node
        else:
            raise MutationResign()
