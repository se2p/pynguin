#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#

"""Utility functions for standard library ast nodes."""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING, TypeVar, cast

_T = TypeVar("_T", bound=ast.AST)

if TYPE_CHECKING:
    from collections.abc import Iterator


def _is_dataclass(class_node: ast.ClassDef) -> bool:
    """Whether the class carries a ``@dataclass`` decorator.

    Recognises ``@dataclass``, ``@dataclasses.dataclass`` and their called
    forms (e.g. ``@dataclass(frozen=True)``).
    """
    for decorator in class_node.decorator_list:
        target = decorator.func if isinstance(decorator, ast.Call) else decorator
        if isinstance(target, ast.Name) and target.id == "dataclass":
            return True
        if isinstance(target, ast.Attribute) and target.attr == "dataclass":
            return True
    return False


def _is_class_var(annotation: ast.expr) -> bool:
    """Whether an annotation is ``ClassVar`` / ``ClassVar[...]`` (any import form)."""
    if isinstance(annotation, ast.Subscript):
        annotation = annotation.value
    if isinstance(annotation, ast.Name):
        return annotation.id == "ClassVar"
    if isinstance(annotation, ast.Attribute):
        return annotation.attr == "ClassVar"
    return False


def _flatten_target(target: ast.expr) -> list[ast.expr]:
    """Flatten tuple/list assignment targets into their leaf expressions."""
    if isinstance(target, (ast.Tuple, ast.List)):
        leaves: list[ast.expr] = []
        for element in target.elts:
            leaves.extend(_flatten_target(element))
        return leaves
    return [target]


def _self_assigned_names(class_node: ast.ClassDef) -> Iterator[str]:
    """Yield names assigned to ``self.<attr>`` in the class's own methods."""
    for item in class_node.body:
        if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for node in ast.walk(item):
            targets: list[ast.expr] = []
            if isinstance(node, ast.Assign):
                targets = list(node.targets)
            elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
                targets = [node.target]
            for target in (leaf for tgt in targets for leaf in _flatten_target(tgt)):
                if (
                    isinstance(target, ast.Attribute)
                    and isinstance(target.value, ast.Name)
                    and target.value.id == "self"
                ):
                    yield target.attr


def _dataclass_field_names(class_node: ast.ClassDef) -> Iterator[str]:
    """Yield annotated ``@dataclass`` field names (excluding ``ClassVar`` fields)."""
    if not _is_dataclass(class_node):
        return
    for item in class_node.body:
        if (
            isinstance(item, ast.AnnAssign)
            and isinstance(item.target, ast.Name)
            and not _is_class_var(item.annotation)
        ):
            yield item.target.id


def instance_attributes(class_node: ast.ClassDef) -> tuple[str, ...]:
    """Names assigned to ``self.<attr>`` in the class's own methods.

    Mirrors ``astroid.ClassDef.instance_attrs`` (own class only, not inherited),
    preserving first-seen order. For ``@dataclass`` classes the class-level
    annotated fields are included as well (excluding ``ClassVar`` fields), since
    astroid's dataclass support synthesises the corresponding ``__init__``
    assignments.

    Args:
        class_node: The ClassDef AST node.

    Returns:
        A tuple of instance attribute names.
    """
    names: dict[str, None] = {}
    for name in (*_dataclass_field_names(class_node), *_self_assigned_names(class_node)):
        names.setdefault(name, None)
    return tuple(names)


def nodes_of_class(tree: ast.AST, types: type[_T] | tuple[type[_T], ...]) -> Iterator[_T]:
    """Yield all nodes (recursively, preorder DFS) that are instances of ``types``.

    Args:
        tree: The AST tree root.
        types: Type or tuple of types to match.

    Yields:
        Nodes matching types.
    """
    stack = [tree]
    while stack:
        node = stack.pop()
        if isinstance(node, types):
            yield cast("_T", node)
        # Push children in reverse order to visit them left-to-right
        stack.extend(reversed(list(ast.iter_child_nodes(node))))


def scope_line_range(node: ast.AST) -> tuple[int, int]:
    """Uniformly retrieve (lineno, end_lineno) for a node.

    Args:
        node: The AST node.

    Returns:
        A tuple of start and end line numbers.
    """
    if isinstance(node, ast.Module):
        # A module's line number is 0 in the AST (matching astroid's
        # ``Module.fromlineno`` and the ``<module>`` code object convention used
        # by the instrumentation transformer), even though its body starts at 1.
        if node.body:
            return 0, node.body[-1].end_lineno or 0
        return 0, 0
    if isinstance(node, ast.match_case):
        start = node.pattern.lineno
        end = node.body[-1].end_lineno or start
        return start, end
    start = getattr(node, "lineno", 1)
    end = getattr(node, "end_lineno", start) or start
    return start, end


def scope_name(node: ast.AST) -> str:
    """Retrieve name of a ScopeNode, matching astroid behavior.

    Args:
        node: The AST node representing the scope.

    Returns:
        The name of the scope.
    """
    if isinstance(node, ast.Module):
        return ""
    if isinstance(node, ast.Lambda):
        return "<lambda>"
    if isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
        lineno = getattr(node, "lineno", 1)
        return f"<generator-{lineno}>"
    return getattr(node, "name", "")
