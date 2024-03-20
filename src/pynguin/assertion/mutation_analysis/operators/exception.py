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

from pynguin.assertion.mutation_analysis.operators.base import MutationOperator, MutationResign


class BaseExceptionHandlerOperator(MutationOperator):

    @staticmethod
    def _replace_exception_body(exception_node: ast.ExceptHandler, body: list[ast.stmt]) -> ast.ExceptHandler:
        return ast.ExceptHandler(type=exception_node.type, name=exception_node.name, lineno=exception_node.lineno,
                                 body=body)


class ExceptionHandlerDeletion(BaseExceptionHandlerOperator):
    def mutate_ExceptHandler(self, node: ast.ExceptHandler) -> ast.ExceptHandler:
        if node.body and isinstance(node.body[0], ast.Raise):
            raise MutationResign()
        return self._replace_exception_body(node, [ast.Raise(lineno=node.body[0].lineno)])


class ExceptionSwallowing(BaseExceptionHandlerOperator):
    def mutate_ExceptHandler(self, node: ast.ExceptHandler) -> ast.ExceptHandler:
        if len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
            raise MutationResign()
        return self._replace_exception_body(node, [ast.Pass(lineno=node.body[0].lineno)])

    @classmethod
    def name(cls) -> str:
        return "EXS"
