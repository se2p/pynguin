#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides statement operators for mutation analysis."""

import ast

from pynguin.assertion.mutation_analysis.operators.base import MutationOperator, copy_node


class ReturnValueReplacement(MutationOperator):
    """A class that mutates return statements by replacing their value with None."""

    def mutate_Return(self, node: ast.Return) -> ast.Return | None:  # noqa: N802
        """Mutate a Return statement by replacing its value with None.

        Args:
            node: The Return statement to mutate.

        Returns:
            The mutated statement, or None if the statement should not be mutated.
        """
        if node.value is None:
            return None
        if isinstance(node.value, ast.Constant) and node.value.value is None:
            return None
        mutated = copy_node(node)
        mutated.value = ast.Constant(value=None)
        return mutated


class AssertionRemoval(MutationOperator):
    """A class that mutates assert statements by removing them."""

    def mutate_Assert(self, node: ast.Assert) -> ast.Pass:  # noqa: N802
        """Mutate an Assert statement by replacing it with a Pass statement.

        Args:
            node: The Assert statement to mutate.

        Returns:
            The mutated statement.
        """
        return ast.Pass(lineno=node.lineno)


class MatchCaseDeletion(MutationOperator):
    """A class that mutates match statements by removing cases."""

    def mutate_Match_remove_first(  # noqa: N802
        self, node: ast.Match
    ) -> ast.Match | None:
        """Mutate a match statement by removing the first case.

        Args:
            node: The match statement to mutate.

        Returns:
            The mutated statement, or None if fewer than 2 cases exist.
        """
        if not hasattr(ast, "Match") or len(node.cases) < 2:
            return None
        mutated = copy_node(node)
        mutated.cases = list(node.cases[1:])
        return mutated

    def mutate_Match_remove_last(  # noqa: N802
        self, node: ast.Match
    ) -> ast.Match | None:
        """Mutate a match statement by removing the last case.

        Args:
            node: The match statement to mutate.

        Returns:
            The mutated statement, or None if fewer than 2 cases exist.
        """
        if not hasattr(ast, "Match") or len(node.cases) < 2:
            return None
        mutated = copy_node(node)
        mutated.cases = list(node.cases[:-1])
        return mutated
