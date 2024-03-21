
#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019-2023 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides classes for mutation testing.

Comes from https://github.com/se2p/mutpy-pynguin/blob/main/mutpy/operators/base.py.
"""
from __future__ import annotations

import abc
import ast
import copy
import types

from typing import Generator, Callable, TypeVar

from pynguin.assertion.mutation_analysis import utils


class Mutation:
    def __init__(self, operator: type[MutationOperator], node: ast.AST, visitor: Callable[[], None] | None = None):
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


T = TypeVar("T", bound=ast.AST)


class MutationOperator:
    def mutate(
        self,
        node: T,
        sampler: utils.RandomSampler | None = None,
        module: types.ModuleType | None = None,
        only_mutation: Mutation | None = None
    ):
        self.sampler = sampler
        self.only_mutation = only_mutation
        self.module = module
        for new_node in self.visit(node):
            yield Mutation(operator=self.__class__, node=self.current_node, visitor=self.visitor), new_node

    def visit(self, node: T) -> Generator[ast.AST, None, None]:
        if self.only_mutation and self.only_mutation.node != node and self.only_mutation.node not in node.children:
            return

        self.fix_lineno(node)

        visitors = self.find_visitors(node)

        if not visitors:
            yield from self.generic_visit(node)
            return

        for visitor in visitors:
            if self.sampler and not self.sampler.is_mutation_time():
                yield from self.generic_visit(node)
                continue

            if (
                self.only_mutation
                and (
                    self.only_mutation.node != node
                    or self.only_mutation.visitor != visitor.__name__
                )
            ):
                yield from self.generic_visit(node)
                continue

            new_node = visitor(node)

            if new_node is None:
                yield from self.generic_visit(node)
                continue

            self.visitor = visitor.__name__
            self.current_node = node
            self.fix_node_internals(node, new_node)
            ast.fix_missing_locations(new_node)

            yield new_node

            yield from self.generic_visit(node)

    def generic_visit(self, node: ast.AST) -> Generator[ast.AST, None, None]:
        for field, old_value in ast.iter_fields(node):
            if isinstance(old_value, list):
                generator = self.generic_visit_list(old_value)
            elif isinstance(old_value, ast.AST):
                generator = self.generic_visit_real_node(node, field, old_value)
            else:
                generator = []

            for _ in generator:
                yield node

    def generic_visit_list(self, old_value: list[ast.AST | None]) -> Generator[None, None, None]:
        old_values_copy = old_value[:]
        for position, value in enumerate(old_values_copy):
            if isinstance(value, ast.AST):
                for new_value in self.visit(value):
                    if not isinstance(new_value, ast.AST):
                        old_value[position:position + 1] = new_value
                    else:
                        old_value[position] = new_value

                    yield
                    old_value[:] = old_values_copy

    def generic_visit_real_node(self, node: ast.AST, field: str, old_value: ast.AST) -> Generator[None, None, None]:
        for new_node in self.visit(old_value):
            if new_node is None:
                delattr(node, field)
            else:
                setattr(node, field, new_node)
            yield
            setattr(node, field, old_value)

    def fix_lineno(self, node: ast.AST) -> None:
        if not hasattr(node, 'lineno') and getattr(node, 'parent', None) is not None and hasattr(node.parent, 'lineno'):
            node.lineno = node.parent.lineno

    def fix_node_internals(self, old_node: ast.AST, new_node: ast.AST) -> None:
        if not hasattr(new_node, 'parent'):
            new_node.children = old_node.children
            new_node.parent = old_node.parent
        if not hasattr(new_node, 'lineno') and hasattr(old_node, 'lineno'):
            new_node.lineno = old_node.lineno
        if hasattr(old_node, 'marker'):
            new_node.marker = old_node.marker

    def find_visitors(self, node: T) -> list[Callable[[T], ast.AST | None]]:
        node_name = node.__class__.__name__
        method_prefix = f"mutate_{node_name}"
        return [
            visitor
            for attr in dir(self)
            if attr.startswith(method_prefix) and callable(visitor := getattr(self, attr))
        ]

    def set_lineno(self, node: ast.AST, lineno: int) -> None:
        for n in ast.walk(node):
            if hasattr(n, 'lineno'):
                n.lineno = lineno

    def shift_lines(self, nodes: list[ast.AST], shift_by: int = 1) -> None:
        for node in nodes:
            ast.increment_lineno(node, shift_by)


class AbstractUnaryOperatorDeletion(abc.ABC, MutationOperator):
    @abc.abstractmethod
    def get_operator_type(self) -> type[ast.unaryop]:
        pass

    def mutate_UnaryOp(self, node: ast.UnaryOp) -> ast.expr | None:
        if not isinstance(node.op, self.get_operator_type()):
            return None

        return node.operand
