#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019-2023 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides classes for mutation testing.

Comes from https://github.com/se2p/mutpy-pynguin/blob/main/mutpy/operators/misc.py.
Comes from https://github.com/se2p/mutpy-pynguin/blob/main/mutpy/utils.py.
"""

import ast

from pynguin.assertion.mutation_analysis.operators.arithmetic import AbstractArithmeticOperatorReplacement
from pynguin.assertion.mutation_analysis.operators.base import MutationOperator


def is_docstring(node: ast.AST) -> bool:
    if not isinstance(node, ast.Str):
        return False

    expression_node = getattr(node, "parent")

    if not isinstance(expression_node, ast.Expr):
        return False

    def_node = getattr(expression_node, "parent")

    return (
        isinstance(def_node, (ast.FunctionDef, ast.ClassDef, ast.Module))
        and def_node.body
        and def_node.body[0] == expression_node
    )


class AssignmentOperatorReplacement(AbstractArithmeticOperatorReplacement):
    def should_mutate(self, node: ast.AST) -> bool:
        parent = getattr(node, "parent")
        return isinstance(parent, ast.AugAssign)


class BreakContinueReplacement(MutationOperator):
    def mutate_Break(self, node: ast.Break) -> ast.Continue:
        return ast.Continue()

    def mutate_Continue(self, node: ast.Continue) -> ast.Break:
        return ast.Break()


class ConstantReplacement(MutationOperator):
    FIRST_CONST_STRING = "mutpy"
    SECOND_CONST_STRING = "python"

    def help_str(self, node: ast.Constant) -> str | None:
        if is_docstring(node):
            return None

        if node.value == self.FIRST_CONST_STRING:
            return self.SECOND_CONST_STRING

        return self.FIRST_CONST_STRING

    @staticmethod
    def help_str_empty(node: ast.Constant) -> str | None:
        if not node.value or is_docstring(node):
            return None

        return ""

    def mutate_Constant_num(self, node: ast.Constant) -> ast.Constant | None:
        value = node.value

        if not isinstance(value, (int, float)) or isinstance(value, bool):
            return None

        return ast.Constant(value + 1)

    def mutate_Constant_str(self, node: ast.Constant) -> ast.Constant | None:
        if not isinstance(node.value, str):
            return None

        new_value = self.help_str(node)

        if new_value is None:
            return None

        return ast.Constant(new_value)

    def mutate_Constant_str_empty(self, node: ast.Constant) -> ast.Constant | None:
        if not isinstance(node.value, str):
            return None

        new_value = self.help_str_empty(node)

        if new_value is None:
            return None

        return ast.Constant(new_value)

    def mutate_Num(self, node: ast.Num) -> ast.Num:
        return ast.Num(node.value + 1)

    def mutate_Str(self, node: ast.Str) -> ast.Str | None:
        new_value = self.help_str(node)

        if new_value is None:
            return None

        return ast.Str(new_value)

    def mutate_Str_empty(self, node: ast.Str) -> ast.Str | None:
        new_value = self.help_str_empty(node)

        if new_value is None:
            return None

        return ast.Str(new_value)


class SliceIndexRemove(MutationOperator):
    def mutate_Slice_remove_lower(self, node: ast.Slice) -> ast.Slice | None:
        if node.lower is None:
            return None

        return ast.Slice(lower=None, upper=node.upper, step=node.step)

    def mutate_Slice_remove_upper(self, node: ast.Slice) -> ast.Slice | None:
        if node.upper is None:
            return None

        return ast.Slice(lower=node.lower, upper=None, step=node.step)

    def mutate_Slice_remove_step(self, node: ast.Slice) -> ast.Slice | None:
        if node.step is None:
            return None

        return ast.Slice(lower=node.lower, upper=node.upper, step=None)
