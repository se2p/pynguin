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
    def get_operator_type(self):
        return ast.Not

    def mutate_NotIn(self, node):
        return ast.In()


class ConditionalOperatorInsertion(MutationOperator):
    def negate_test(self, node):
        not_node = ast.UnaryOp(op=ast.Not(), operand=node.test)
        node.test = not_node
        return node

    @copy_node
    def mutate_While(self, node):
        return self.negate_test(node)

    @copy_node
    def mutate_If(self, node):
        return self.negate_test(node)

    def mutate_In(self, node):
        return ast.NotIn()


class LogicalConnectorReplacement(MutationOperator):
    def mutate_And(self, node):
        return ast.Or()

    def mutate_Or(self, node):
        return ast.And()


class LogicalOperatorDeletion(AbstractUnaryOperatorDeletion):
    def get_operator_type(self):
        return ast.Invert


class LogicalOperatorReplacement(MutationOperator):
    def mutate_BitAnd(self, node):
        return ast.BitOr()

    def mutate_BitOr(self, node):
        return ast.BitAnd()

    def mutate_BitXor(self, node):
        return ast.BitAnd()

    def mutate_LShift(self, node):
        return ast.RShift()

    def mutate_RShift(self, node):
        return ast.LShift()


class RelationalOperatorReplacement(MutationOperator):
    def mutate_Lt(self, node):
        return ast.Gt()

    def mutate_Lt_to_LtE(self, node):
        return ast.LtE()

    def mutate_Gt(self, node):
        return ast.Lt()

    def mutate_Gt_to_GtE(self, node):
        return ast.GtE()

    def mutate_LtE(self, node):
        return ast.GtE()

    def mutate_LtE_to_Lt(self, node):
        return ast.Lt()

    def mutate_GtE(self, node):
        return ast.LtE()

    def mutate_GtE_to_Gt(self, node):
        return ast.Gt()

    def mutate_Eq(self, node):
        return ast.NotEq()

    def mutate_NotEq(self, node):
        return ast.Eq()
