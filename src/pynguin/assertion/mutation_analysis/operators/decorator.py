#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides decorators operators for mutation analysis.

Based on https://github.com/se2p/mutpy-pynguin/blob/main/mutpy/operators/decorator.py
and integrated in Pynguin.
"""

import ast

from pynguin.assertion.mutation_analysis.operators.base import MutationOperator
from pynguin.assertion.mutation_analysis.operators.base import copy_node


class DecoratorDeletion(MutationOperator):
    """A class that mutates decorators by deleting them."""

    def mutate_FunctionDef(self, node: ast.FunctionDef) -> ast.AST | None:  # noqa: N802
        """Mutate a function definition by deleting its decorators.

        Args:
            node: The function definition to mutate.

        Returns:
            The mutated node, or None if the decorators should not be mutated.
        """
        if not node.decorator_list:
            return None

        mutated_node = copy_node(node)
        mutated_node.decorator_list = []
        return mutated_node
