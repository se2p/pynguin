#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
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


def _names_in(node: ast.AST) -> set[str]:
    """Collect the identifiers of all ``Name`` nodes in a subtree.

    Args:
        node: The subtree to search.

    Returns:
        The set of ``Name.id`` values found in the subtree.
    """
    return {child.id for child in ast.walk(node) if isinstance(child, ast.Name)}


def _is_self_referential_multiplication_in_loop(node: ast.Mult) -> bool:
    """Check for a self-feeding multiplication accumulator inside a loop.

    Turning ``Mult`` into ``Pow`` is catastrophic when a multiplication whose
    result is assigned back to one of its own operands runs inside a loop, e.g.
    ``decimal = decimal * base + ...``. As a power this grows the accumulator's
    magnitude super-linearly every iteration, so a single exponentiation soon
    runs for hours in C while holding the GIL, which the in-process execution
    timeout cannot interrupt (see issue #306, residual of #296).

    Detect that pattern statically: the operands of the enclosing multiplication
    ``BinOp`` intersect the target names of the nearest enclosing assignment, and
    that assignment is nested in a ``for``/``while`` loop.

    Args:
        node: The ``Mult`` operator node being considered for mutation.

    Returns:
        ``True`` if the multiplication is a self-referential accumulator inside a
        loop, so the ``Mult -> Pow`` mutation should be skipped.
    """
    binop = getattr(node, "parent", None)
    if not isinstance(binop, ast.BinOp):
        return False

    operand_names = _names_in(binop.left) | _names_in(binop.right)
    if not operand_names:
        return False

    found_self_reference = False
    in_loop = False
    current = getattr(binop, "parent", None)
    while current is not None:
        if not found_self_reference and isinstance(
            current, ast.Assign | ast.AnnAssign | ast.AugAssign
        ):
            targets = current.targets if isinstance(current, ast.Assign) else [current.target]
            target_names = {name for target in targets for name in _names_in(target)}
            if target_names & operand_names:
                found_self_reference = True
        if isinstance(current, ast.For | ast.AsyncFor | ast.While):
            in_loop = True
        current = getattr(current, "parent", None)

    return found_self_reference and in_loop


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

        The mutation is skipped for a self-referential multiplication accumulator
        inside a loop (e.g. ``x = x * y`` in a ``for`` loop), because as a power it
        grows the accumulator super-linearly each iteration and a single
        exponentiation soon blocks for hours in C while holding the GIL, which the
        in-process execution timeout cannot interrupt (issue #306).

        Args:
            node: The Mult operator to mutate.

        Returns:
            The mutated operator, or None if the operator should not be mutated.
        """
        if not self.should_mutate(node):
            return None

        if _is_self_referential_multiplication_in_loop(node):
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
