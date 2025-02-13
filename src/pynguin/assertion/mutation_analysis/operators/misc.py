#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides miscellaneous operators for mutation analysis.

Based on https://github.com/se2p/mutpy-pynguin/blob/main/mutpy/operators/misc.py
and https://github.com/se2p/mutpy-pynguin/blob/main/mutpy/utils.py
and integrated in Pynguin.
"""

import ast

from pynguin.assertion.mutation_analysis.operators.arithmetic import (
    AbstractArithmeticOperatorReplacement,
)
from pynguin.assertion.mutation_analysis.operators.base import MutationOperator


def is_docstring(node: ast.AST) -> bool:
    """Check if the given node is a docstring.

    Args:
        node: The node to check.

    Returns:
        True if the node is a docstring, False otherwise.
    """
    if not isinstance(node, ast.Str):
        return False

    expression_node: ast.AST = node.parent  # type: ignore[attr-defined]

    if not isinstance(expression_node, ast.Expr):
        return False

    def_node: ast.AST = expression_node.parent  # type: ignore[attr-defined]

    return (
        isinstance(def_node, ast.FunctionDef | ast.ClassDef | ast.Module)
        and def_node.body  # type: ignore[return-value]
        and def_node.body[0] == expression_node
    )


class AssignmentOperatorReplacement(AbstractArithmeticOperatorReplacement):
    """A class that mutates assignment operators by replacing them."""

    def should_mutate(self, node: ast.AST) -> bool:  # noqa: D102
        parent = node.parent  # type: ignore[attr-defined]
        return isinstance(parent, ast.AugAssign)


class BreakContinueReplacement(MutationOperator):
    """A class that mutates break and continue statements by replacing them."""

    def mutate_Break(self, node: ast.Break) -> ast.Continue:  # noqa: N802
        """Mutate a Break statement to a Continue statement.

        Args:
            node: The Break statement to mutate.

        Returns:
            The mutated statement.
        """
        return ast.Continue()

    def mutate_Continue(self, node: ast.Continue) -> ast.Break:  # noqa: N802
        """Mutate a Continue statement to a Break statement.

        Args:
            node: The Continue statement to mutate.

        Returns:
            The mutated statement.
        """
        return ast.Break()


class ConstantReplacement(MutationOperator):
    """A class that mutates constants by replacing them."""

    FIRST_CONST_STRING = "mutpy"
    SECOND_CONST_STRING = "python"

    def help_str(self, node: ast.Constant) -> str | None:
        """Help function for mutating strings.

        Args:
            node: The string to mutate.

        Returns:
            The mutated string, or None if the string should not be mutated.
        """
        if is_docstring(node):
            return None

        if node.value == self.FIRST_CONST_STRING:
            return self.SECOND_CONST_STRING

        return self.FIRST_CONST_STRING

    @staticmethod
    def help_str_empty(node: ast.Constant) -> str | None:
        """Help function for mutating empty strings.

        Args:
            node: The string to mutate.

        Returns:
            The mutated string, or None if the string should not be mutated.
        """
        if not node.value or is_docstring(node):
            return None

        return ""

    def mutate_Constant_num(  # noqa: N802
        self, node: ast.Constant
    ) -> ast.Constant | None:
        """Mutate a numeric constant by adding 1.

        Args:
            node: The constant to mutate.

        Returns:
            The mutated constant, or None if the constant should not be mutated.
        """
        value = node.value

        if not isinstance(value, int | float) or isinstance(value, bool):
            return None

        return ast.Constant(value + 1)

    def mutate_Constant_str(  # noqa: N802
        self, node: ast.Constant
    ) -> ast.Constant | None:
        """Mutate a string constant by replacing it.

        Args:
            node: The constant to mutate.

        Returns:
            The mutated constant, or None if the constant should not be mutated.
        """
        if not isinstance(node.value, str):
            return None

        new_value = self.help_str(node)

        if new_value is None:
            return None

        return ast.Constant(new_value)

    def mutate_Constant_str_empty(  # noqa: N802
        self, node: ast.Constant
    ) -> ast.Constant | None:
        """Mutate an empty string constant by replacing it.

        Args:
            node: The constant to mutate.

        Returns:
            The mutated constant, or None if the constant should not be mutated.
        """
        if not isinstance(node.value, str):
            return None

        new_value = self.help_str_empty(node)

        if new_value is None:
            return None

        return ast.Constant(new_value)


class SliceIndexRemove(MutationOperator):
    """A class that mutates slice indices by removing them."""

    def mutate_Slice_remove_lower(  # noqa: N802
        self, node: ast.Slice
    ) -> ast.Slice | None:
        """Mutate a Slice index by removing the lower bound.

        Args:
            node: The Slice index to mutate.

        Returns:
            The mutated index, or None if the index should not be mutated.
        """
        if node.lower is None:
            return None

        return ast.Slice(lower=None, upper=node.upper, step=node.step)

    def mutate_Slice_remove_upper(  # noqa: N802
        self, node: ast.Slice
    ) -> ast.Slice | None:
        """Mutate a Slice index by removing the upper bound.

        Args:
            node: The Slice index to mutate.

        Returns:
            The mutated index, or None if the index should not be mutated.
        """
        if node.upper is None:
            return None

        return ast.Slice(lower=node.lower, upper=None, step=node.step)

    def mutate_Slice_remove_step(  # noqa: N802
        self, node: ast.Slice
    ) -> ast.Slice | None:
        """Mutate a Slice index by removing the step.

        Args:
            node: The Slice index to mutate.

        Returns:
            The mutated index, or None if the index should not be mutated.
        """
        if node.step is None:
            return None

        return ast.Slice(lower=node.lower, upper=node.upper, step=None)
