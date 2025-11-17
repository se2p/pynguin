#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides logical operators for mutation analysis.

Based on https://github.com/se2p/mutpy-pynguin/blob/main/mutpy/operators/logical.py
and integrated in Pynguin.
"""

import ast
from typing import TypeVar

from pynguin.assertion.mutation_analysis.operators.base import (
    AbstractUnaryOperatorDeletion,
    MutationOperator,
    copy_node,
)


class ConditionalOperatorDeletion(AbstractUnaryOperatorDeletion):
    """A class that mutates conditional operators by deleting them."""

    def get_operator_type(self) -> type:
        """Get the operator type."""
        return ast.Not

    def mutate_NotIn(self, node: ast.NotIn) -> ast.In:  # noqa: N802
        """Mutate a NotIn operator to an In operator.

        Args:
            node: The NotIn operator to mutate.

        Returns:
            The mutated operator.
        """
        return ast.In()


T = TypeVar("T", ast.If, ast.While)


def negate_test(node: T) -> T:
    """Negate the test of a node.

    Args:
        node: The node to negate.

    Returns:
        The mutated node.
    """
    mutated_node = copy_node(node)
    not_node = ast.UnaryOp(op=ast.Not(), operand=mutated_node.test)
    mutated_node.test = not_node
    return mutated_node


class ConditionalOperatorInsertion(MutationOperator):
    """A class that mutates conditional operators by inserting them."""

    def mutate_While(self, node: ast.While) -> ast.While:  # noqa: N802
        """Mutate a While node by negating its test.

        Args:
            node: The While node to mutate.

        Returns:
            The mutated node.
        """
        return negate_test(node)

    def mutate_If(self, node: ast.If) -> ast.If:  # noqa: N802
        """Mutate an If node by negating its test.

        Args:
            node: The If node to mutate.

        Returns:
            The mutated node.
        """
        return negate_test(node)

    def mutate_In(self, node: ast.In) -> ast.NotIn:  # noqa: N802
        """Mutate an In operator to a NotIn operator.

        Args:
            node: The In operator to mutate.

        Returns:
            The mutated operator.
        """
        return ast.NotIn()


class LogicalConnectorReplacement(MutationOperator):
    """A class that mutates logical connectors by replacing them."""

    def mutate_And(self, node: ast.And) -> ast.Or:  # noqa: N802
        """Mutate an And operator to an Or operator.

        Args:
            node: The And operator to mutate.

        Returns:
            The mutated operator.
        """
        return ast.Or()

    def mutate_Or(self, node: ast.Or) -> ast.And:  # noqa: N802
        """Mutate an Or operator to an And operator.

        Args:
            node: The Or operator to mutate.

        Returns:
            The mutated operator.
        """
        return ast.And()


class LogicalOperatorDeletion(AbstractUnaryOperatorDeletion):
    """A class that mutates logical operators by deleting them."""

    def get_operator_type(self) -> type:  # noqa: D102
        return ast.Invert


class LogicalOperatorReplacement(MutationOperator):
    """A class that mutates logical operators by replacing them."""

    def mutate_BitAnd(self, node: ast.BitAnd) -> ast.BitOr:  # noqa: N802
        """Mutate a BitAnd operator to a BitOr operator.

        Args:
            node: The BitAnd operator to mutate.

        Returns:
            The mutated operator.
        """
        return ast.BitOr()

    def mutate_BitOr(self, node: ast.BitOr) -> ast.BitAnd:  # noqa: N802
        """Mutate a BitOr operator to a BitAnd operator.

        Args:
            node: The BitOr operator to mutate.

        Returns:
            The mutated operator.
        """
        return ast.BitAnd()

    def mutate_BitXor(self, node: ast.BitXor) -> ast.BitAnd:  # noqa: N802
        """Mutate a BitXor operator to a BitAnd operator.

        Args:
            node: The BitXor operator to mutate.

        Returns:
            The mutated operator.
        """
        return ast.BitAnd()

    def mutate_LShift(self, node: ast.LShift) -> ast.RShift:  # noqa: N802
        """Mutate a LShift operator to a RShift operator.

        Args:
            node: The LShift operator to mutate.

        Returns:
            The mutated operator.
        """
        return ast.RShift()

    def mutate_RShift(self, node: ast.RShift) -> ast.LShift:  # noqa: N802
        """Mutate a RShift operator to a LShift operator.

        Args:
            node: The RShift operator to mutate.

        Returns:
            The mutated operator.
        """
        return ast.LShift()


class RelationalOperatorReplacement(MutationOperator):
    """A class that mutates relational operators by replacing them."""

    def mutate_Lt(self, node: ast.Lt) -> ast.Gt:  # noqa: N802
        """Mutate a Lt operator to a Gt operator.

        Args:
            node: The Lt operator to mutate.

        Returns:
            The mutated operator.
        """
        return ast.Gt()

    def mutate_Lt_to_LtE(self, node: ast.Lt) -> ast.LtE:  # noqa: N802
        """Mutate a Lt operator to a LtE operator.

        Args:
            node: The Lt operator to mutate.

        Returns:
            The mutated operator.
        """
        return ast.LtE()

    def mutate_Gt(self, node: ast.Gt) -> ast.Lt:  # noqa: N802
        """Mutate a Gt operator to a Lt operator.

        Args:
            node: The Gt operator to mutate.

        Returns:
            The mutated operator.
        """
        return ast.Lt()

    def mutate_Gt_to_GtE(self, node: ast.Gt) -> ast.GtE:  # noqa: N802
        """Mutate a Gt operator to a GtE operator.

        Args:
            node: The Gt operator to mutate.

        Returns:
            The mutated operator.
        """
        return ast.GtE()

    def mutate_LtE(self, node: ast.LtE) -> ast.GtE:  # noqa: N802
        """Mutate a LtE operator to a GtE operator.

        Args:
            node: The LtE operator to mutate.

        Returns:
            The mutated operator.
        """
        return ast.GtE()

    def mutate_LtE_to_Lt(self, node: ast.LtE) -> ast.Lt:  # noqa: N802
        """Mutate a LtE operator to a Lt operator.

        Args:
            node: The LtE operator to mutate.

        Returns:
            The mutated operator.
        """
        return ast.Lt()

    def mutate_GtE(self, node: ast.GtE) -> ast.LtE:  # noqa: N802
        """Mutate a GtE operator to a LtE operator.

        Args:
            node: The GtE operator to mutate.

        Returns:
            The mutated operator.
        """
        return ast.LtE()

    def mutate_GtE_to_Gt(self, node: ast.GtE) -> ast.Gt:  # noqa: N802
        """Mutate a GtE operator to a Gt operator.

        Args:
            node: The GtE operator to mutate.

        Returns:
            The mutated operator.
        """
        return ast.Gt()

    def mutate_Eq(self, node: ast.Eq) -> ast.NotEq:  # noqa: N802
        """Mutate an Eq operator to a NotEq operator.

        Args:
            node: The Eq operator to mutate.

        Returns:
            The mutated operator.
        """
        return ast.NotEq()

    def mutate_NotEq(self, node: ast.NotEq) -> ast.Eq:  # noqa: N802
        """Mutate a NotEq operator to an Eq operator.

        Args:
            node: The NotEq operator to mutate.

        Returns:
            The mutated operator.
        """
        return ast.Eq()
