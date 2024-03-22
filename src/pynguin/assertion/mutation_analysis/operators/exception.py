#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019-2023 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides classes for mutation testing.

Comes from https://github.com/se2p/mutpy-pynguin/blob/main/mutpy/operators/exception.py.
"""

import ast

from pynguin.assertion.mutation_analysis.operators.base import MutationOperator


def replace_exception_handler(
    exception_handler: ast.ExceptHandler,
    body: list[ast.stmt],
) -> ast.ExceptHandler:
    return ast.ExceptHandler(
        type=exception_handler.type,
        name=exception_handler.name,
        lineno=exception_handler.lineno,
        body=body,
    )


class ExceptionHandlerDeletion(MutationOperator):
    def mutate_ExceptHandler(self, node: ast.ExceptHandler) -> ast.ExceptHandler | None:
        if not node.body:
            return None

        first_statement = node.body[0]

        if isinstance(first_statement, ast.Raise):
            return None

        return replace_exception_handler(
            node, [ast.Raise(lineno=first_statement.lineno)]
        )


class ExceptionSwallowing(MutationOperator):
    def mutate_ExceptHandler(self, node: ast.ExceptHandler) -> ast.ExceptHandler | None:
        if not node.body:
            return None

        first_statement = node.body[0]

        if len(node.body) == 1 and isinstance(first_statement, ast.Pass):
            return None

        return replace_exception_handler(
            node, [ast.Pass(lineno=first_statement.lineno)]
        )
