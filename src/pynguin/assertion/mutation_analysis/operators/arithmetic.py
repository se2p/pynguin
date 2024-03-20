#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019-2023 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides classes for mutation testing.

Comes from https://github.com/se2p/mutpy-pynguin/blob/main/mutpy/operators/arithmetic.py.
"""

import ast

from pynguin.assertion.mutation_analysis.operators.base import MutationResign, MutationOperator, AbstractUnaryOperatorDeletion


class ArithmeticOperatorDeletion(AbstractUnaryOperatorDeletion):
    def get_operator_type(self):
        return ast.UAdd, ast.USub


class AbstractArithmeticOperatorReplacement(MutationOperator):
    def should_mutate(self, node: ast.AST) -> bool:
        raise NotImplementedError()

    def mutate_Add(self, node: ast.Add) -> ast.Sub:
        if self.should_mutate(node):
            return ast.Sub()
        raise MutationResign()

    def mutate_Sub(self, node: ast.Sub) -> ast.Add:
        if self.should_mutate(node):
            return ast.Add()
        raise MutationResign()

    def mutate_Mult_to_Div(self, node: ast.Mult) -> ast.Div:
        if self.should_mutate(node):
            return ast.Div()
        raise MutationResign()

    def mutate_Mult_to_FloorDiv(self, node: ast.Mult) -> ast.FloorDiv:
        if self.should_mutate(node):
            return ast.FloorDiv()
        raise MutationResign()

    def mutate_Mult_to_Pow(self, node: ast.Mult) -> ast.Pow:
        if self.should_mutate(node):
            return ast.Pow()
        raise MutationResign()

    def mutate_Div_to_Mult(self, node: ast.Div) -> ast.Mult:
        if self.should_mutate(node):
            return ast.Mult()
        raise MutationResign()

    def mutate_Div_to_FloorDiv(self, node: ast.Div) -> ast.FloorDiv:
        if self.should_mutate(node):
            return ast.FloorDiv()
        raise MutationResign()

    def mutate_FloorDiv_to_Div(self, node: ast.FloorDiv) -> ast.Div:
        if self.should_mutate(node):
            return ast.Div()
        raise MutationResign()

    def mutate_FloorDiv_to_Mult(self, node: ast.FloorDiv) -> ast.Mult:
        if self.should_mutate(node):
            return ast.Mult()
        raise MutationResign()

    def mutate_Mod(self, node: ast.Mod) -> ast.Mult:
        if self.should_mutate(node):
            return ast.Mult()
        raise MutationResign()

    def mutate_Pow(self, node: ast.Pow) -> ast.Mult:
        if self.should_mutate(node):
            return ast.Mult()
        raise MutationResign()


class ArithmeticOperatorReplacement(AbstractArithmeticOperatorReplacement):
    def should_mutate(self, node: ast.AST) -> bool:
        return not isinstance(node.parent, ast.AugAssign)

    def mutate_USub(self, node: ast.USub) -> ast.UAdd:
        return ast.UAdd()

    def mutate_UAdd(self, node: ast.UAdd) -> ast.USub:
        return ast.USub()
