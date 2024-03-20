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
    def should_mutate(self, node):
        return isinstance(node.parent, ast.AugAssign)

    @classmethod
    def name(cls):
        return 'ASR'


class BreakContinueReplacement(MutationOperator):
    def mutate_Break(self, node):
        return ast.Continue()

    def mutate_Continue(self, node):
        return ast.Break()


class ConstantReplacement(MutationOperator):
    FIRST_CONST_STRING = 'mutpy'
    SECOND_CONST_STRING = 'python'

    def help_str(self, node):
        if utils.is_docstring(node):
            raise MutationResign()

        if node.s != self.FIRST_CONST_STRING:
            return self.FIRST_CONST_STRING
        else:
            return self.SECOND_CONST_STRING

    def help_str_empty(self, node):
        if not node.s or utils.is_docstring(node):
            raise MutationResign()
        return ''

    def mutate_Constant_num(self, node):
        if isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return ast.Constant(n=node.n + 1)
        else:
            raise MutationResign()

    def mutate_Constant_str(self, node):
        if isinstance(node.value, str):
            return ast.Constant(s=self.help_str(node))
        else:
            raise MutationResign()

    def mutate_Constant_str_empty(self, node):
        if isinstance(node.value, str):
            return ast.Constant(s=self.help_str_empty(node))
        else:
            raise MutationResign()

    def mutate_Num(self, node):
        return ast.Num(n=node.n + 1)

    def mutate_Str(self, node):
        return ast.Str(s=self.help_str(node))

    def mutate_Str_empty(self, node):
        return ast.Str(s=self.help_str_empty(node))

    @classmethod
    def name(cls):
        return 'CRP'


class SliceIndexRemove(MutationOperator):
    def mutate_Slice_remove_lower(self, node):
        if not node.lower:
            raise MutationResign()

        return ast.Slice(lower=None, upper=node.upper, step=node.step)

    def mutate_Slice_remove_upper(self, node):
        if not node.upper:
            raise MutationResign()

        return ast.Slice(lower=node.lower, upper=None, step=node.step)

    def mutate_Slice_remove_step(self, node):
        if not node.step:
            raise MutationResign()

        return ast.Slice(lower=node.lower, upper=node.upper, step=None)


class SelfVariableDeletion(MutationOperator):
    def mutate_Attribute(self, node):
        try:
            if node.value.id == 'self':
                return ast.Name(id=node.attr, ctx=ast.Load())
            else:
                raise MutationResign()
        except AttributeError:
            raise MutationResign()


class StatementDeletion(MutationOperator):
    def mutate_Assign(self, node):
        return ast.Pass()

    def mutate_Return(self, node):
        return ast.Pass()

    def mutate_Expr(self, node):
        if utils.is_docstring(node.value):
            raise MutationResign()
        return ast.Pass()

    @classmethod
    def name(cls):
        return 'SDL'
