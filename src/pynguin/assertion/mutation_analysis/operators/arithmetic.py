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
    def should_mutate(self, node):
        raise NotImplementedError()

    def mutate_Add(self, node):
        if self.should_mutate(node):
            return ast.Sub()
        raise MutationResign()

    def mutate_Sub(self, node):
        if self.should_mutate(node):
            return ast.Add()
        raise MutationResign()

    def mutate_Mult_to_Div(self, node):
        if self.should_mutate(node):
            return ast.Div()
        raise MutationResign()

    def mutate_Mult_to_FloorDiv(self, node):
        if self.should_mutate(node):
            return ast.FloorDiv()
        raise MutationResign()

    def mutate_Mult_to_Pow(self, node):
        if self.should_mutate(node):
            return ast.Pow()
        raise MutationResign()

    def mutate_Div_to_Mult(self, node):
        if self.should_mutate(node):
            return ast.Mult()
        raise MutationResign()

    def mutate_Div_to_FloorDiv(self, node):
        if self.should_mutate(node):
            return ast.FloorDiv()
        raise MutationResign()

    def mutate_FloorDiv_to_Div(self, node):
        if self.should_mutate(node):
            return ast.Div()
        raise MutationResign()

    def mutate_FloorDiv_to_Mult(self, node):
        if self.should_mutate(node):
            return ast.Mult()
        raise MutationResign()

    def mutate_Mod(self, node):
        if self.should_mutate(node):
            return ast.Mult()
        raise MutationResign()

    def mutate_Pow(self, node):
        if self.should_mutate(node):
            return ast.Mult()
        raise MutationResign()


class ArithmeticOperatorReplacement(AbstractArithmeticOperatorReplacement):
    def should_mutate(self, node):
        return not isinstance(node.parent, ast.AugAssign)

    def mutate_USub(self, node):
        return ast.UAdd()

    def mutate_UAdd(self, node):
        return ast.USub()
