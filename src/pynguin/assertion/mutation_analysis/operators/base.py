#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides base classes for mutation operators.

Based on https://github.com/se2p/mutpy-pynguin/blob/main/mutpy/operators/base.py
and integrated in Pynguin.
"""

from __future__ import annotations

import abc
import ast
import copy
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    import types
    from collections.abc import Callable, Generator, Iterable


def fix_lineno(node: ast.AST, fixing_node: ast.AST | None) -> None:
    """Fix the line number of a node using a fixing node.

    Args:
        node: The node to fix.
        fixing_node: The node to use for fixing the line number.
    """
    node_lineno = getattr(node, "lineno", None)
    node_end_lineno = getattr(node, "end_lineno", None)

    # Both missing -> try fixing_node
    if node_lineno is None and node_end_lineno is None:
        fixing_lineno = getattr(fixing_node, "lineno", None)
        fixing_end_lineno = getattr(fixing_node, "end_lineno", None)

        if fixing_lineno is not None:
            node.lineno = fixing_lineno  # type: ignore[attr-defined]
        elif fixing_end_lineno is not None:
            node.lineno = fixing_end_lineno  # type: ignore[attr-defined]

        if fixing_end_lineno is not None:
            node.end_lineno = fixing_end_lineno  # type: ignore[attr-defined]
        elif fixing_lineno is not None:
            node.end_lineno = fixing_lineno  # type: ignore[attr-defined]

        return

    # Only one missing -> sync values
    if node_end_lineno is None and node_lineno is not None:
        node.end_lineno = node_lineno  # type: ignore[attr-defined]
    elif node_lineno is None and node_end_lineno is not None:
        node.lineno = node_end_lineno  # type: ignore[attr-defined]
    elif node_end_lineno is not None and node_lineno is not None and node_end_lineno < node_lineno:
        node.end_lineno = node_lineno  # type: ignore[attr-defined]


def fix_node_internals(old_node: ast.AST, new_node: ast.AST) -> None:
    """Fix the internals of a node.

    Args:
        old_node: The old node.
        new_node: The new node.
    """
    if not hasattr(new_node, "parent"):
        new_node.children = old_node.children  # type: ignore[attr-defined]
        new_node.parent = old_node.parent  # type: ignore[attr-defined]

    fix_lineno(new_node, old_node)

    if hasattr(old_node, "marker"):
        new_node.marker = old_node.marker  # type: ignore[attr-defined]


def set_lineno(node: ast.AST, lineno: int) -> None:
    """Set the line number of a node.

    Args:
        node: The node to set the line number for.
        lineno: The line number to set.
    """
    for child_node in ast.walk(node):
        if hasattr(child_node, "lineno"):
            child_node.lineno = lineno


T = TypeVar("T", bound=ast.AST)


def shift_lines(nodes: list[T], shift_by: int = 1) -> None:
    """Shift the line numbers of a list of nodes.

    Args:
        nodes: The nodes to shift.
        shift_by: The amount to shift by.
    """
    for node in nodes:
        ast.increment_lineno(node, shift_by)


@dataclass(frozen=True)
class Mutation:
    """Represents a mutation."""

    node: ast.AST
    replacement_node: ast.AST
    operator: type[MutationOperator]
    visitor_name: str

    def __post_init__(self):
        """Initialize the mutation.

        Raises:
            ValueError: If the visitor is not found in the operator.
        """
        if self.visitor_name not in dir(self.operator):
            raise ValueError(f"Visitor {self.visitor_name} not found in operator {self.operator}")


def copy_node(node: T) -> T:
    """Copy a node.

    Args:
        node: The node to copy.

    Returns:
        The copied node.
    """
    parent = node.parent  # type: ignore[attr-defined]
    return copy.deepcopy(
        node,
        memo={
            id(parent): parent,
        },
    )


class MutationOperator:
    """A class that represents a mutation operator."""

    @classmethod
    def mutate(
        cls,
        node: ast.AST,
        module: types.ModuleType,
        only_mutation: Mutation | None = None,
    ) -> Generator[tuple[Mutation, ast.AST]]:
        """Mutate a node.

        This method will temporarily modify the node provided and yield itself modified
        with the mutations. If you want to keep the original node while using the
        generator, you should copy it before passing it to this method.

        Args:
            node: The node to mutate.
            module: The module to use.
            only_mutation: The mutation to apply.

        Yields:
            A tuple containing the mutation and the mutated node.
        """
        operator = cls(module, only_mutation)

        for (
            current_node,
            replacement_node,
            mutated_node,
            visitor_name,
        ) in operator.visit(node):
            yield (
                Mutation(current_node, replacement_node, cls, visitor_name),
                mutated_node,
            )

    def __init__(
        self,
        module: types.ModuleType,
        only_mutation: Mutation | None,
    ) -> None:
        """Initializes the operator.

        Args:
            module: The module to use.
            only_mutation: The mutation to apply.
        """
        self.module = module
        self.only_mutation = only_mutation

    def visit(self, node: ast.AST) -> Generator[tuple[ast.AST, ast.AST, ast.AST, str]]:
        """Visit a node.

        This method will temporarily modify the node provided and yield itself modified
        with other information. If you want to keep the original node while using the
        generator, you should copy it before passing it to this method.

        Args:
            node: The node to visit.

        Yields:
            A tuple (current node, replacement node, mutated node, visitor name).
        """
        node_children = node.children  # type: ignore[attr-defined]

        if (
            self.only_mutation
            and self.only_mutation.node != node
            and self.only_mutation.node not in node_children
        ):
            return

        fix_lineno(node, getattr(node, "parent", None))

        for visitor in self._find_visitors(node):
            if (
                self.only_mutation is None
                or (
                    self.only_mutation.node == node
                    and self.only_mutation.visitor_name == visitor.__name__
                )
            ) and (mutated_node := visitor(node)) is not None:
                fix_node_internals(node, mutated_node)
                ast.fix_missing_locations(mutated_node)

                yield node, mutated_node, mutated_node, visitor.__name__

        yield from self._generic_visit(node)

    def _generic_visit(self, node: ast.AST) -> Generator[tuple[ast.AST, ast.AST, ast.AST, str]]:
        for field, old_value in ast.iter_fields(node):
            generator: Iterable[tuple[ast.AST, ast.AST, str]]
            if isinstance(old_value, list):
                generator = self._generic_visit_list(old_value)
            elif isinstance(old_value, ast.AST):
                generator = self._generic_visit_real_node(node, field, old_value)
            else:
                generator = ()

            for current_node, replacement_node, visitor_name in generator:
                yield current_node, replacement_node, node, visitor_name

    def _generic_visit_list(self, old_value: list) -> Generator[tuple[ast.AST, ast.AST, str]]:
        for position, value in enumerate(old_value.copy()):
            if isinstance(value, ast.AST):
                for (
                    current_node,
                    replacement_node,
                    mutated_node,
                    visitor_name,
                ) in self.visit(value):
                    old_value[position] = mutated_node
                    yield current_node, replacement_node, visitor_name

                old_value[position] = value

    def _generic_visit_real_node(
        self, node: ast.AST, field: str, old_value: ast.AST
    ) -> Generator[tuple[ast.AST, ast.AST, str]]:
        for current_node, replacement_node, mutated_node, visitor_name in self.visit(old_value):
            setattr(node, field, mutated_node)
            yield current_node, replacement_node, visitor_name

        setattr(node, field, old_value)

    def _find_visitors(self, node: T) -> list[Callable[[T], ast.AST | None]]:
        node_name = node.__class__.__name__
        method_prefix_pattern = re.compile(f"^mutate_{node_name}(_\\w+)?$")
        return [
            visitor
            for attr in dir(self)
            if method_prefix_pattern.match(attr) is not None
            and callable(visitor := getattr(self, attr))
        ]


class AbstractUnaryOperatorDeletion(abc.ABC, MutationOperator):
    """An abstract class that mutates unary operators by deleting them."""

    @abc.abstractmethod
    def get_operator_type(self) -> type:
        """Get the operator type.

        Returns:
            The operator type.
        """

    def mutate_UnaryOp(self, node: ast.UnaryOp) -> ast.expr | None:  # noqa: N802
        """Mutate a unary operator.

        Args:
            node: The node to mutate.

        Returns:
            The mutated node, or None if the node should not be mutated.
        """
        if not isinstance(node.op, self.get_operator_type()):
            return None

        return node.operand
