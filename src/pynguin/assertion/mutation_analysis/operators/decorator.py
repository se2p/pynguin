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

from pynguin.assertion.mutation_analysis.operators.base import MutationOperator, copy_node


class DecoratorDeletion(MutationOperator):
    @copy_node
    def mutate_FunctionDef(self, node: ast.FunctionDef) -> ast.AST | None:
        if not node.decorator_list:
            return None

        node.decorator_list = []
        return node
