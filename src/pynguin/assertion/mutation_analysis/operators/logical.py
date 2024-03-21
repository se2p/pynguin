#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019-2023 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides classes for mutation testing.

Comes from https://github.com/se2p/mutpy-pynguin/blob/main/mutpy/operators/logical.py.
"""

import ast

from pynguin.assertion.mutation_analysis.operators.base import MutationOperator, AbstractUnaryOperatorDeletion, copy_node


class ConditionalOperatorDeletion(AbstractUnaryOperatorDeletion):
    def get_operator_type(self) -> type:
        return ast.Not

    def mutate_NotIn(self, node: ast.NotIn) -> ast.In:
        return ast.In()


class ConditionalOperatorInsertion(MutationOperator):
    def negate_test(self, node: ast.If | ast.While) -> ast.If | ast.While:
        mutated_node = copy_node(node)
        not_node = ast.UnaryOp(op=ast.Not(), operand=mutated_node.test)
        mutated_node.test = not_node
        return mutated_node

    def mutate_While(self, node: ast.While) -> ast.While:
        return self.negate_test(node)

    def mutate_If(self, node: ast.If) -> ast.If:
        return self.negate_test(node)

    def mutate_In(self, node: ast.In) -> ast.NotIn:
        return ast.NotIn()


class LogicalConnectorReplacement(MutationOperator):
    def mutate_And(self, node: ast.And) -> ast.Or:
        return ast.Or()

    def mutate_Or(self, node: ast.Or) -> ast.And:
        return ast.And()


class LogicalOperatorDeletion(AbstractUnaryOperatorDeletion):
    def get_operator_type(self) -> type:
        return ast.Invert


class LogicalOperatorReplacement(MutationOperator):
    def mutate_BitAnd(self, node: ast.BitAnd) -> ast.BitOr:
        return ast.BitOr()

    def mutate_BitOr(self, node: ast.BitOr) -> ast.BitAnd:
        return ast.BitAnd()

    def mutate_BitXor(self, node: ast.BitXor) -> ast.BitAnd:
        return ast.BitAnd()

    def mutate_LShift(self, node: ast.LShift) -> ast.RShift:
        return ast.RShift()

    def mutate_RShift(self, node: ast.RShift) -> ast.LShift:
        return ast.LShift()


class RelationalOperatorReplacement(MutationOperator):
    def mutate_Lt(self, node: ast.Lt) -> ast.Gt:
        return ast.Gt()

    def mutate_Lt_to_LtE(self, node: ast.Lt) -> ast.LtE:
        return ast.LtE()

    def mutate_Gt(self, node: ast.Gt) -> ast.Lt:
        return ast.Lt()

    def mutate_Gt_to_GtE(self, node: ast.Gt) -> ast.GtE:
        return ast.GtE()

    def mutate_LtE(self, node: ast.LtE) -> ast.GtE:
        return ast.GtE()

    def mutate_LtE_to_Lt(self, node: ast.LtE) -> ast.Lt:
        return ast.Lt()

    def mutate_GtE(self, node: ast.GtE) -> ast.LtE:
        return ast.LtE()

    def mutate_GtE_to_Gt(self, node: ast.GtE) -> ast.Gt:
        return ast.Gt()

    def mutate_Eq(self, node: ast.Eq) -> ast.NotEq:
        return ast.NotEq()

    def mutate_NotEq(self, node: ast.NotEq) -> ast.Eq:
        return ast.Eq()
