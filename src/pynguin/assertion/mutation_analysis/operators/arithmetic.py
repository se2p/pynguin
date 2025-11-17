#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides arithmetic operators for mutation analysis.

Based on https://github.com/se2p/mutpy-pynguin/blob/main/mutpy/operators/arithmetic.py
and integrated in Pynguin.
"""

import abc
import ast

from pynguin.assertion.mutation_analysis.operators.base import (
    AbstractUnaryOperatorDeletion,
    MutationOperator,
)


class ArithmeticOperatorDeletion(AbstractUnaryOperatorDeletion):
    """A class that mutate arithmetic operators by deleting them."""

    def get_operator_type(self) -> type:  # noqa: D102
        return ast.UAdd | ast.USub  # type: ignore[return-value]


class AbstractArithmeticOperatorReplacement(abc.ABC, MutationOperator):
    """An abstract class that mutates arithmetic operators by replacing them."""

    @abc.abstractmethod
    def should_mutate(self, node: ast.AST) -> bool:
        """Check if the operator should be mutated.

        Args:
            node: The node to check.

        Returns:
            True if the operator should be mutated, False otherwise.
        """

    def mutate_Add(self, node: ast.Add) -> ast.Sub | None:  # noqa: N802
        """Mutate an Add operator to a Sub operator.

        Args:
            node: The Add operator to mutate.

        Returns:
            The mutated operator, or None if the operator should not be mutated.
        """
        if not self.should_mutate(node):
            return None

        return ast.Sub()

    def mutate_Sub(self, node: ast.Sub) -> ast.Add | None:  # noqa: N802
        """Mutate a Sub operator to an Add operator.

        Args:
            node: The Sub operator to mutate.

        Returns:
            The mutated operator, or None if the operator should not be mutated.
        """
        if not self.should_mutate(node):
            return None

        return ast.Add()

    def mutate_Mult_to_Div(self, node: ast.Mult) -> ast.Div | None:  # noqa: N802
        """Mutate a Mult operator to a Div operator.

        Args:
            node: The Mult operator to mutate.

        Returns:
            The mutated operator, or None if the operator should not be mutated.
        """
        if not self.should_mutate(node):
            return None

        return ast.Div()

    def mutate_Mult_to_FloorDiv(  # noqa: N802
        self, node: ast.Mult
    ) -> ast.FloorDiv | None:
        """Mutate a Mult operator to a FloorDiv operator.

        Args:
            node: The Mult operator to mutate.

        Returns:
            The mutated operator, or None if the operator should not be mutated.
        """
        if not self.should_mutate(node):
            return None

        return ast.FloorDiv()

    def mutate_Mult_to_Pow(self, node: ast.Mult) -> ast.Pow | None:  # noqa: N802
        """Mutate a Mult operator to a Pow operator.

        Args:
            node: The Mult operator to mutate.

        Returns:
            The mutated operator, or None if the operator should not be mutated.
        """
        if not self.should_mutate(node):
            return None

        return ast.Pow()

    def mutate_Div_to_Mult(self, node: ast.Div) -> ast.Mult | None:  # noqa: N802
        """Mutate a Div operator to a Mult operator.

        Args:
            node: The Div operator to mutate.

        Returns:
            The mutated operator, or None if the operator should not be mutated.
        """
        if not self.should_mutate(node):
            return None

        return ast.Mult()

    def mutate_Div_to_FloorDiv(  # noqa: N802
        self, node: ast.Div
    ) -> ast.FloorDiv | None:
        """Mutate a Div operator to a FloorDiv operator.

        Args:
            node: The Div operator to mutate.

        Returns:
            The mutated operator, or None if the operator should not be mutated.
        """
        if not self.should_mutate(node):
            return None

        return ast.FloorDiv()

    def mutate_FloorDiv_to_Div(  # noqa: N802
        self, node: ast.FloorDiv
    ) -> ast.Div | None:
        """Mutate a FloorDiv operator to a Div operator.

        Args:
            node: The FloorDiv operator to mutate.

        Returns:
            The mutated operator, or None if the operator should not be mutated.
        """
        if not self.should_mutate(node):
            return None

        return ast.Div()

    def mutate_FloorDiv_to_Mult(  # noqa: N802
        self, node: ast.FloorDiv
    ) -> ast.Mult | None:
        """Mutate a FloorDiv operator to a Mult operator.

        Args:
            node: The FloorDiv operator to mutate.

        Returns:
            The mutated operator, or None if the operator should not be mutated.
        """
        if not self.should_mutate(node):
            return None

        return ast.Mult()

    def mutate_Mod(self, node: ast.Mod) -> ast.Mult | None:  # noqa: N802
        """Mutate a Mod operator to a Mult operator.

        Args:
            node: The Mod operator to mutate.

        Returns:
            The mutated operator, or None if the operator should not be mutated.
        """
        if not self.should_mutate(node):
            return None

        return ast.Mult()

    def mutate_Pow(self, node: ast.Pow) -> ast.Mult | None:  # noqa: N802
        """Mutate a Pow operator to a Mult operator.

        Args:
            node: The Pow operator to mutate.

        Returns:
            The mutated operator, or None if the operator should not be mutated.
        """
        if not self.should_mutate(node):
            return None

        return ast.Mult()


class ArithmeticOperatorReplacement(AbstractArithmeticOperatorReplacement):
    """A class that mutates arithmetic operators by replacing them."""

    def should_mutate(self, node: ast.AST) -> bool:  # noqa: D102
        parent = node.parent  # type: ignore[attr-defined]
        return not isinstance(parent, ast.AugAssign)

    def mutate_USub(self, node: ast.USub) -> ast.UAdd:  # noqa: N802
        """Mutate a USub operator to a UAdd operator.

        Args:
            node: The USub operator to mutate.

        Returns:
            The mutated operator.
        """
        return ast.UAdd()

    def mutate_UAdd(self, node: ast.UAdd) -> ast.USub:  # noqa: N802
        """Mutate a UAdd operator to a USub operator.

        Args:
            node: The UAdd operator to mutate.

        Returns:
            The mutated operator.
        """
        return ast.USub()
