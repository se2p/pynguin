#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides exception operators for mutation analysis.

Based on https://github.com/se2p/mutpy-pynguin/blob/main/mutpy/operators/exception.py
and integrated in Pynguin.
"""

import ast

from pynguin.assertion.mutation_analysis.operators.base import MutationOperator


def replace_exception_handler(
    exception_handler: ast.ExceptHandler,
    body: list[ast.stmt],
) -> ast.ExceptHandler:
    """Replace an exception handler with a new body.

    Args:
        exception_handler: The exception handler to replace.
        body: The new body.

    Returns:
        The new exception handler.
    """
    return ast.ExceptHandler(
        type=exception_handler.type,
        name=exception_handler.name,
        lineno=exception_handler.lineno,
        body=body,
    )


class ExceptionHandlerDeletion(MutationOperator):
    """A class that mutates exception handlers by deleting them."""

    def mutate_ExceptHandler(  # noqa: N802
        self, node: ast.ExceptHandler
    ) -> ast.ExceptHandler | None:
        """Mutate an exception handler by deleting it.

        Args:
            node: The exception handler to mutate.

        Returns:
            The mutated node, or None if the exception handler should not be mutated.
        """
        if not node.body:
            return None

        first_statement = node.body[0]

        if isinstance(first_statement, ast.Raise):
            return None

        return replace_exception_handler(node, [ast.Raise(lineno=first_statement.lineno)])


class ExceptionSwallowing(MutationOperator):
    """A class that mutates exception handlers by ignoring the caught exception."""

    def mutate_ExceptHandler(  # noqa: N802
        self, node: ast.ExceptHandler
    ) -> ast.ExceptHandler | None:
        """Mutate an exception handler by ignoring the caught exception.

        Args:
            node: The exception handler to mutate.

        Returns:
            The mutated node, or None if the exception handler should not be mutated.
        """
        if not node.body:
            return None

        first_statement = node.body[0]

        if len(node.body) == 1 and isinstance(first_statement, ast.Pass):
            return None

        return replace_exception_handler(node, [ast.Pass(lineno=first_statement.lineno)])
