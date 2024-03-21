
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

from pynguin.assertion.mutation_analysis.sampler import RandomSampler


def fix_lineno(node: ast.AST) -> None:
    parent = getattr(node, "parent")
    if not hasattr(node, "lineno") and parent is not None and hasattr(parent, "lineno"):
        parent_lineno = getattr(parent, "lineno")
        setattr(node, "lineno", parent_lineno)


def fix_node_internals(old_node: ast.AST, new_node: ast.AST) -> None:
    if not hasattr(new_node, "parent"):
        old_node_children = getattr(old_node, "children")
        old_node_parent = getattr(old_node, "parent")
        setattr(new_node, "children", old_node_children)
        setattr(new_node, "parent", old_node_parent)

    if not hasattr(new_node, "lineno") and hasattr(old_node, "lineno"):
        old_node_lineno = getattr(old_node, "lineno")
        setattr(new_node, "lineno", old_node_lineno)

    if hasattr(old_node, "marker"):
        old_node_marker = getattr(old_node, "marker")
        setattr(new_node, "marker", old_node_marker)


def set_lineno(node: ast.AST, lineno: int) -> None:
    for child_node in ast.walk(node):
        if hasattr(child_node, "lineno"):
            setattr(child_node, "lineno", lineno)


def shift_lines(nodes: list[ast.AST], shift_by: int = 1) -> None:
    for node in nodes:
        ast.increment_lineno(node, shift_by)


class Mutation:
    def __init__(self, node: ast.AST, operator: type[MutationOperator], visitor_name: str) -> None:
        self.node = node
        self.operator = operator
        self.visitor_name = visitor_name


T = TypeVar("T", bound=ast.AST)


def copy_node(node: T) -> T:
    parent = getattr(node, "parent")
    return copy.deepcopy(node, memo={
        id(parent): parent,
    })


class MutationOperator:
    @classmethod
    def mutate(
        cls,
        node: T,
        sampler: RandomSampler | None = None,
        module: types.ModuleType | None = None,
        only_mutation: Mutation | None = None
    ):
        operator = cls(sampler, module, only_mutation)

        for current_node, mutated_node, visitor_name in operator.visit(node):
            yield Mutation(current_node, cls, visitor_name), mutated_node

    def __init__(
        self,
        sampler: RandomSampler | None,
        module: types.ModuleType | None,
        only_mutation: Mutation | None,
    ) -> None:
        self.sampler = sampler
        self.module = module
        self.only_mutation = only_mutation

    def visit(self, node: T) -> Generator[tuple[ast.AST, ast.AST, str], None, None]:
        if self.only_mutation and self.only_mutation.node != node and self.only_mutation.node not in node.children:
            return

        fix_lineno(node)

        visitors = self.find_visitors(node)

        if not visitors:
            yield from self.generic_visit(node)
            return

        for visitor in visitors:
            if (
                (
                    self.sampler is None
                    or self.sampler.is_mutation_time()
                )
                and (
                    self.only_mutation is None
                    or (
                        self.only_mutation.node == node
                        and self.only_mutation.visitor_name == visitor.__name__
                    )
                )
                and (mutated_node := visitor(node)) is not None
            ):
                fix_node_internals(node, mutated_node)
                ast.fix_missing_locations(mutated_node)

                yield node, mutated_node, visitor.__name__

            yield from self.generic_visit(node)

    def generic_visit(self, node: ast.AST) -> Generator[tuple[ast.AST, ast.AST, str], None, None]:
        for field, old_value in ast.iter_fields(node):
            if isinstance(old_value, list):
                generator = self.generic_visit_list(old_value)
            elif isinstance(old_value, ast.AST):
                generator = self.generic_visit_real_node(node, field, old_value)
            else:
                generator = []

            for current_node, visitor_name in generator:
                yield current_node, node, visitor_name

    def generic_visit_list(self, old_value: list) -> Generator[tuple[ast.AST, str], None, None]:
        for position, value in enumerate(old_value.copy()):
            if isinstance(value, ast.AST):
                for current_node, mutated_node, visitor_name in self.visit(value):
                    old_value[position] = mutated_node
                    yield current_node, visitor_name

                old_value[position] = value

    def generic_visit_real_node(self, node: ast.AST, field: str, old_value: ast.AST) -> Generator[tuple[ast.AST, str], None, None]:
        for current_node, mutated_node, visitor_name in self.visit(old_value):
            setattr(node, field, mutated_node)
            yield current_node, visitor_name

        setattr(node, field, old_value)

    def find_visitors(self, node: T) -> list[Callable[[T], ast.AST | None]]:
        node_name = node.__class__.__name__
        method_prefix = f"mutate_{node_name}"
        return [
            visitor
            for attr in dir(self)
            if attr.startswith(method_prefix) and callable(visitor := getattr(self, attr))
        ]


class AbstractUnaryOperatorDeletion(abc.ABC, MutationOperator):
    @abc.abstractmethod
    def get_operator_type(self) -> type[ast.unaryop]:
        pass

    def mutate_UnaryOp(self, node: ast.UnaryOp) -> ast.expr | None:
        if not isinstance(node.op, self.get_operator_type()):
            return None

        return node.operand
