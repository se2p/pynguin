
#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019-2023 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides classes for mutation testing.

Comes from https://github.com/se2p/mutpy-pynguin/blob/main/mutpy/operators/base.py.
"""

import ast
import copy
import re

from pynguin.assertion.mutation_analysis import utils


class MutationResign(Exception):
    pass


class Mutation:
    def __init__(self, operator, node, visitor=None):
        self.operator = operator
        self.node = node
        self.visitor = visitor


def copy_node(mutate):
    def f(self, node):
        copied_node = copy.deepcopy(node, memo={
            id(node.parent): node.parent,
        })
        return mutate(self, copied_node)

    return f


class MutationOperator:
    def mutate(self, node, to_mutate=None, sampler=None, coverage_injector=None, module=None, only_mutation=None):
        self.to_mutate = to_mutate
        self.sampler = sampler
        self.only_mutation = only_mutation
        self.coverage_injector = coverage_injector
        self.module = module
        for new_node in self.visit(node):
            yield Mutation(operator=self.__class__, node=self.current_node, visitor=self.visitor), new_node

    def visit(self, node):
        if self.has_notmutate(node) or (self.coverage_injector and not self.coverage_injector.is_covered(node)):
            return
        if self.only_mutation and self.only_mutation.node != node and self.only_mutation.node not in node.children:
            return
        self.fix_lineno(node)
        visitors = self.find_visitors(node)
        if visitors:
            for visitor in visitors:
                try:
                    if self.sampler and not self.sampler.is_mutation_time():
                        raise MutationResign
                    if self.only_mutation and \
                            (self.only_mutation.node != node or self.only_mutation.visitor != visitor.__name__):
                        raise MutationResign
                    new_node = visitor(node)
                    self.visitor = visitor.__name__
                    self.current_node = node
                    self.fix_node_internals(node, new_node)
                    ast.fix_missing_locations(new_node)
                    yield new_node
                except MutationResign:
                    pass
                finally:
                    for new_node in self.generic_visit(node):
                        yield new_node
        else:
            for new_node in self.generic_visit(node):
                yield new_node

    def generic_visit(self, node):
        for field, old_value in ast.iter_fields(node):
            if isinstance(old_value, list):
                generator = self.generic_visit_list(old_value)
            elif isinstance(old_value, ast.AST):
                generator = self.generic_visit_real_node(node, field, old_value)
            else:
                generator = []

            for _ in generator:
                yield node

    def generic_visit_list(self, old_value):
        old_values_copy = old_value[:]
        for position, value in enumerate(old_values_copy):
            if isinstance(value, ast.AST):
                for new_value in self.visit(value):
                    if not isinstance(new_value, ast.AST):
                        old_value[position:position + 1] = new_value
                    elif value is None:
                        del old_value[position]
                    else:
                        old_value[position] = new_value

                    yield
                    old_value[:] = old_values_copy

    def generic_visit_real_node(self, node, field, old_value):
        for new_node in self.visit(old_value):
            if new_node is None:
                delattr(node, field)
            else:
                setattr(node, field, new_node)
            yield
            setattr(node, field, old_value)

    def has_notmutate(self, node):
        try:
            for decorator in node.decorator_list:
                if decorator.id == utils.notmutate.__name__:
                    return True
            return False
        except AttributeError:
            return False

    def fix_lineno(self, node):
        if not hasattr(node, 'lineno') and getattr(node, 'parent', None) is not None and hasattr(node.parent, 'lineno'):
            node.lineno = node.parent.lineno

    def fix_node_internals(self, old_node, new_node):
        if not hasattr(new_node, 'parent'):
            new_node.children = old_node.children
            new_node.parent = old_node.parent
        if not hasattr(new_node, 'lineno') and hasattr(old_node, 'lineno'):
            new_node.lineno = old_node.lineno
        if hasattr(old_node, 'marker'):
            new_node.marker = old_node.marker

    def find_visitors(self, node):
        method_prefix = 'mutate_' + node.__class__.__name__
        return self.getattrs_like(method_prefix)

    def getattrs_like(ob, attr_like):
        pattern = re.compile(attr_like + "($|(_\w+)+$)")
        return [getattr(ob, attr) for attr in dir(ob) if pattern.match(attr)]

    def set_lineno(self, node, lineno):
        for n in ast.walk(node):
            if hasattr(n, 'lineno'):
                n.lineno = lineno

    def shift_lines(self, nodes, shift_by=1):
        for node in nodes:
            ast.increment_lineno(node, shift_by)

    @classmethod
    def name(cls):
        return ''.join([c for c in cls.__name__ if str.isupper(c)])

    @classmethod
    def long_name(cls):
        return ' '.join(map(str.lower, (re.split('([A-Z][a-z]*)', cls.__name__)[1::2])))


class AbstractUnaryOperatorDeletion(MutationOperator):
    def mutate_UnaryOp(self, node):
        if isinstance(node.op, self.get_operator_type()):
            return node.operand
        raise MutationResign()
