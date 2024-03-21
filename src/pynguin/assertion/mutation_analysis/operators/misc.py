#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019-2023 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides classes for mutation testing.

Comes from https://github.com/se2p/mutpy-pynguin/blob/main/mutpy/operators/misc.py.
"""

import ast

from pynguin.assertion.mutation_analysis import utils
from pynguin.assertion.mutation_analysis.operators.arithmetic import AbstractArithmeticOperatorReplacement
from pynguin.assertion.mutation_analysis.operators.base import MutationOperator, MutationResign


class AssignmentOperatorReplacement(AbstractArithmeticOperatorReplacement):
    def should_mutate(self, node: ast.AST) -> bool:
        return isinstance(node.parent, ast.AugAssign)


class BreakContinueReplacement(MutationOperator):
    def mutate_Break(self, node: ast.Break) -> ast.Continue:
        return ast.Continue()

    def mutate_Continue(self, node: ast.Continue) -> ast.Break:
        return ast.Break()


class ConstantReplacement(MutationOperator):
    FIRST_CONST_STRING = 'mutpy'
    SECOND_CONST_STRING = 'python'

    def help_str(self, node: ast.AST) -> str:
        if utils.is_docstring(node):
            raise MutationResign()

        if node.s != self.FIRST_CONST_STRING:
            return self.FIRST_CONST_STRING
        else:
            return self.SECOND_CONST_STRING

    def help_str_empty(self, node: ast.AST) -> str:
        if not node.s or utils.is_docstring(node):
            raise MutationResign()
        return ''

    def mutate_Constant_num(self, node: ast.Constant) -> ast.Constant:
        if isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return ast.Constant(n=node.n + 1)
        else:
            raise MutationResign()

    def mutate_Constant_str(self, node: ast.Constant) -> ast.Constant:
        if isinstance(node.value, str):
            return ast.Constant(s=self.help_str(node))
        else:
            raise MutationResign()

    def mutate_Constant_str_empty(self, node: ast.Constant) -> ast.Constant:
        if isinstance(node.value, str):
            return ast.Constant(s=self.help_str_empty(node))
        else:
            raise MutationResign()

    def mutate_Num(self, node: ast.Num) -> ast.Num:
        return ast.Num(n=node.n + 1)

    def mutate_Str(self, node: ast.Str) -> ast.Str:
        return ast.Str(s=self.help_str(node))

    def mutate_Str_empty(self, node: ast.Str) -> ast.Str:
        return ast.Str(s=self.help_str_empty(node))


class SliceIndexRemove(MutationOperator):
    def mutate_Slice_remove_lower(self, node: ast.Slice) -> ast.Slice:
        if not node.lower:
            raise MutationResign()

        return ast.Slice(lower=None, upper=node.upper, step=node.step)

    def mutate_Slice_remove_upper(self, node: ast.Slice) -> ast.Slice:
        if not node.upper:
            raise MutationResign()

        return ast.Slice(lower=node.lower, upper=None, step=node.step)

    def mutate_Slice_remove_step(self, node: ast.Slice) -> ast.Slice:
        if not node.step:
            raise MutationResign()

        return ast.Slice(lower=node.lower, upper=node.upper, step=None)


class SelfVariableDeletion(MutationOperator):
    def mutate_Attribute(self, node: ast.Attribute) -> ast.Name:
        try:
            if node.value.id == 'self':
                return ast.Name(id=node.attr, ctx=ast.Load())
            else:
                raise MutationResign()
        except AttributeError:
            raise MutationResign()


class StatementDeletion(MutationOperator):
    def mutate_Assign(self, node: ast.Assign) -> ast.Pass:
        return ast.Pass()

    def mutate_Return(self, node: ast.Return) -> ast.Pass:
        return ast.Pass()

    def mutate_Expr(self, node: ast.Expr) -> ast.Pass:
        if utils.is_docstring(node.value):
            raise MutationResign()
        return ast.Pass()
