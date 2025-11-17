#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides inheritance operators for mutation analysis.

Based on https://github.com/se2p/mutpy-pynguin/blob/main/mutpy/operators/inheritance.py
and integrated in Pynguin.
"""

import ast
import functools
from collections.abc import Iterable
from typing import Any, cast

from pynguin.assertion.mutation_analysis.operators.base import (
    MutationOperator,
    copy_node,
    set_lineno,
    shift_lines,
)
from pynguin.assertion.mutation_analysis.transformer import ParentNodeTransformer


def getattr_rec(obj: object, attr: Iterable[str]) -> Any:
    """Get an attribute recursively.

    Args:
        obj: The object to get the attribute from.
        attr: The attribute to get.

    Returns:
        The attribute.
    """
    return functools.reduce(getattr, attr, obj)


class AbstractOverriddenElementModification(MutationOperator):
    """An abstract class that provides a method to check if an element is overridden."""

    def is_overridden(self, node: ast.AST, name: str) -> bool | None:
        """Check if a method is overridden.

        Args:
            node: The node to check.
            name: The name of the method to check.

        Returns:
            True if the method is overridden, False if it is not, None on error.
        """
        parent: ast.AST = node.parent  # type: ignore[attr-defined]

        if not isinstance(parent, ast.ClassDef) or not isinstance(
            node, ast.FunctionDef | ast.AsyncFunctionDef | ast.Assign
        ):
            return None

        parent_names: list[str] = []

        while parent is not None:
            if not isinstance(parent, ast.Module):
                parent_names.append(parent.name)  # type: ignore[attr-defined]
            if not isinstance(parent, ast.ClassDef) and not isinstance(parent, ast.Module):
                return None
            parent = parent.parent  # type: ignore[attr-defined,union-attr]

        try:
            klass = getattr_rec(self.module, reversed(parent_names))
        except AttributeError:
            return None

        return any(hasattr(base_klass, name) for base_klass in type.mro(klass)[1:-1])


class HidingVariableDeletion(AbstractOverriddenElementModification):
    """A class that mutates hiding variables by deleting them."""

    def mutate_Assign(self, node: ast.Assign) -> ast.stmt | None:  # noqa: N802
        """Mutate an assignment by deleting a hiding variable.

        Args:
            node: The assignment to mutate.

        Returns:
            The mutated node, or None if the node should not be mutated.
        """
        if len(node.targets) != 1:
            return None

        first_expression = node.targets[0]

        if isinstance(first_expression, ast.Name):
            overridden = self.is_overridden(node, first_expression.id)

            if overridden is None or not overridden:
                return None

            return ast.Pass()

        if isinstance(first_expression, ast.Tuple) and isinstance(node.value, ast.Tuple):
            return self.mutate_unpack(node)

        return None

    def mutate_unpack(self, node: ast.Assign) -> ast.stmt | None:
        """Mutate an assignment by deleting a hiding variable in an unpacking.

        Args:
            node: The assignment to mutate.

        Returns:
            The mutated node, or None if the node should not be mutated.
        """
        if not node.targets:
            return None

        mutated_node = copy_node(node)

        target = cast("ast.List | ast.Tuple | ast.Set", mutated_node.targets[0])
        value = cast("ast.List | ast.Tuple | ast.Set", mutated_node.value)

        new_targets: list[ast.expr] = []
        new_values: list[ast.expr] = []
        for target_element, value_element in zip(target.elts, value.elts, strict=False):
            if not isinstance(target_element, ast.Name) or not isinstance(value_element, ast.expr):
                continue

            overridden = self.is_overridden(mutated_node, target_element.id)

            if overridden is None:
                return None

            if not overridden:
                new_targets.append(target_element)
                new_values.append(value_element)

        if len(new_targets) == len(target.elts):
            return None

        if not new_targets:
            return ast.Pass()
        if len(new_targets) == 1 and len(new_values) == 1:
            mutated_node.targets = new_targets
            mutated_node.value = new_values[0]
            return mutated_node
        target.elts = new_targets
        value.elts = new_values
        return mutated_node


def is_super_call(node: ast.FunctionDef, stmt: ast.stmt) -> bool:
    """Check if a statement is a super call.

    Args:
        node: The function definition to check.
        stmt: The statement to check.

    Returns:
        True if the statement is a super call, False otherwise.
    """
    return (
        isinstance(stmt, ast.Expr)
        and isinstance(stmt.value, ast.Call)
        and isinstance(stmt.value.func, ast.Attribute)
        and isinstance(stmt.value.func.value, ast.Call)
        and isinstance(stmt.value.func.value.func, ast.Name)
        and stmt.value.func.value.func.id == "super"
        and stmt.value.func.attr == node.name
    )


def get_super_call(node: ast.FunctionDef) -> tuple[int, ast.stmt] | None:
    """Get the super call from a function definition.

    Args:
        node: The function definition to get the super call from.

    Returns:
        The index and the statement of the super call, or None if it does not exist.
    """
    for index, stmt in enumerate(node.body):
        if is_super_call(node, stmt):
            return index, stmt
    return None


class AbstractSuperCallingModification(MutationOperator):
    """A class that provides methods to mutate super calls."""

    def should_mutate(self, node: ast.FunctionDef) -> bool:
        """Check if the node should be mutated.

        Args:
            node: The node to check.

        Returns:
            True if the node should be mutated, False otherwise.
        """
        parent = node.parent  # type: ignore[attr-defined]
        return isinstance(parent, ast.ClassDef)


class OverriddenMethodCallingPositionChange(AbstractSuperCallingModification):
    """A class that mutates the position of the super call in an overridden method."""

    def should_mutate(self, node: ast.FunctionDef) -> bool:  # noqa: D102
        return super().should_mutate(node) and len(node.body) > 1

    def mutate_FunctionDef(  # noqa: N802
        self, node: ast.FunctionDef
    ) -> ast.FunctionDef | None:
        """Mutate the position of the super call in an overridden method.

        Args:
            node: The function definition to mutate.

        Returns:
            The mutated node, or None if the node should not be mutated.
        """
        if not self.should_mutate(node) or not node.body:
            return None

        mutated_node = copy_node(node)

        super_call = get_super_call(mutated_node)

        if super_call is None:
            return None

        index, statement = super_call

        del mutated_node.body[index]

        if index == 0:
            set_lineno(statement, mutated_node.body[-1].lineno)
            shift_lines(mutated_node.body, -1)
            mutated_node.body.append(statement)
        else:
            set_lineno(statement, mutated_node.body[0].lineno)
            shift_lines(mutated_node.body, 1)
            mutated_node.body.insert(0, statement)

        return mutated_node


class OverridingMethodDeletion(AbstractOverriddenElementModification):
    """A class that mutates overriding methods by deleting them."""

    def mutate_FunctionDef(  # noqa: N802
        self, node: ast.FunctionDef
    ) -> ast.Pass | None:
        """Mutate a function definition by deleting it.

        Args:
            node: The function definition to mutate.

        Returns:
            The mutated node, or None if the node should not be mutated.
        """
        overridden = self.is_overridden(node, node.name)

        if overridden is None or not overridden:
            return None

        return ast.Pass()


class SuperCallingDeletion(AbstractSuperCallingModification):
    """A class that mutates super calls by deleting them."""

    def mutate_FunctionDef(  # noqa: N802
        self, node: ast.FunctionDef
    ) -> ast.FunctionDef | None:
        """Mutate a function definition by deleting the super call.

        Args:
            node: The function definition to mutate.

        Returns:
            The mutated node, or None if the node should not be mutated.
        """
        if not self.should_mutate(node) or not node.body:
            return None

        mutated_node = copy_node(node)

        super_call = get_super_call(mutated_node)

        if super_call is None:
            return None

        index, _ = super_call

        mutated_node.body[index] = ast.Pass(lineno=mutated_node.body[index].lineno)

        return mutated_node


class SuperCallingInsert(AbstractSuperCallingModification, AbstractOverriddenElementModification):
    """A class that mutates super calls by inserting them."""

    def mutate_FunctionDef(  # noqa: N802
        self, node: ast.FunctionDef
    ) -> ast.FunctionDef | None:
        """Mutate a function definition by inserting the super call.

        Args:
            node: The function definition to mutate.

        Returns:
            The mutated node, or None if the node should not be mutated.
        """
        overridden = self.is_overridden(node, node.name)

        if not self.should_mutate(node) or not node.body or overridden is None or not overridden:
            return None

        mutated_node = copy_node(node)

        super_call = get_super_call(mutated_node)

        if super_call is not None:
            return None

        mutated_node.body.insert(0, self._create_super_call(mutated_node))
        shift_lines(mutated_node.body[1:], 1)

        return mutated_node

    def _create_super_call(self, node: ast.FunctionDef) -> ast.Expr:
        module = ParentNodeTransformer.create_ast(f"super().{node.name}()")

        assert module.body

        super_call = module.body[0]

        assert isinstance(super_call, ast.Expr)

        super_call_value = super_call.value

        assert isinstance(super_call_value, ast.Call)

        for arg in node.args.args[1 : -len(node.args.defaults) or None]:
            super_call_value.args.append(ast.Name(id=arg.arg, ctx=ast.Load()))

        for arg, default in zip(
            node.args.args[-len(node.args.defaults) :], node.args.defaults, strict=False
        ):
            super_call_value.keywords.append(ast.keyword(arg=arg.arg, value=default))

        for arg, default in zip(  # type: ignore[assignment]
            node.args.kwonlyargs, node.args.kw_defaults, strict=False
        ):
            super_call_value.keywords.append(ast.keyword(arg=arg.arg, value=default))

        if node.args.vararg is not None:
            self._add_vararg_to_super_call(super_call_value, node.args.vararg)

        if node.args.kwarg is not None:
            self._add_kwarg_to_super_call(super_call_value, node.args.kwarg)

        set_lineno(super_call, node.body[0].lineno)

        return super_call

    @staticmethod
    def _add_kwarg_to_super_call(super_call_value: ast.Call, kwarg: ast.arg) -> None:
        super_call_value.keywords.append(
            ast.keyword(arg=None, value=ast.Name(id=kwarg.arg, ctx=ast.Load()))
        )

    @staticmethod
    def _add_vararg_to_super_call(super_call_value: ast.Call, vararg: ast.arg) -> None:
        super_call_value.args.append(
            ast.Starred(ctx=ast.Load(), value=ast.Name(id=vararg.arg, ctx=ast.Load()))
        )
