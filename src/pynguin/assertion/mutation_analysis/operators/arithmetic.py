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

from pynguin.assertion.mutation_analysis.operators.base import (
    AbstractUnaryOperatorDeletion,
)
from pynguin.assertion.mutation_analysis.operators.base import MutationOperator


class ArithmeticOperatorDeletion(AbstractUnaryOperatorDeletion):
    def get_operator_type(self):
        return ast.UAdd, ast.USub


class AbstractArithmeticOperatorReplacement(MutationOperator):
    def should_mutate(self, node: ast.AST) -> bool:
        raise NotImplementedError()

    def mutate_Add(self, node: ast.Add) -> ast.Sub | None:
        if not self.should_mutate(node):
            return None

        return ast.Sub()

    def mutate_Sub(self, node: ast.Sub) -> ast.Add | None:
        if not self.should_mutate(node):
            return None

        return ast.Add()

    def mutate_Mult_to_Div(self, node: ast.Mult) -> ast.Div | None:
        if not self.should_mutate(node):
            return None

        return ast.Div()

    def mutate_Mult_to_FloorDiv(self, node: ast.Mult) -> ast.FloorDiv | None:
        if not self.should_mutate(node):
            return None

        return ast.FloorDiv()

    def mutate_Mult_to_Pow(self, node: ast.Mult) -> ast.Pow | None:
        if not self.should_mutate(node):
            return None

        return ast.Pow()

    def mutate_Div_to_Mult(self, node: ast.Div) -> ast.Mult | None:
        if not self.should_mutate(node):
            return None

        return ast.Mult()

    def mutate_Div_to_FloorDiv(self, node: ast.Div) -> ast.FloorDiv | None:
        if not self.should_mutate(node):
            return None

        return ast.FloorDiv()

    def mutate_FloorDiv_to_Div(self, node: ast.FloorDiv) -> ast.Div | None:
        if not self.should_mutate(node):
            return None

        return ast.Div()

    def mutate_FloorDiv_to_Mult(self, node: ast.FloorDiv) -> ast.Mult | None:
        if not self.should_mutate(node):
            return None

        return ast.Mult()

    def mutate_Mod(self, node: ast.Mod) -> ast.Mult | None:
        if not self.should_mutate(node):
            return None

        return ast.Mult()

    def mutate_Pow(self, node: ast.Pow) -> ast.Mult | None:
        if not self.should_mutate(node):
            return None

        return ast.Mult()


class ArithmeticOperatorReplacement(AbstractArithmeticOperatorReplacement):
    def should_mutate(self, node: ast.AST) -> bool:
        parent = getattr(node, "parent")
        return not isinstance(parent, ast.AugAssign)

    def mutate_USub(self, node: ast.USub) -> ast.UAdd:
        return ast.UAdd()

    def mutate_UAdd(self, node: ast.UAdd) -> ast.USub:
        return ast.USub()
