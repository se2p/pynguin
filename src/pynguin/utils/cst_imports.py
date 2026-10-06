# This file is part of the Pynguin automated unit test generation framework.
# Copyright (C) 2019–2026 Pynguin Contributors
# SPDX-License-Identifier: MIT
#
"""Provides libcst helpers for import statements and name bindings."""

from __future__ import annotations

import importlib.util
import logging

import libcst as cst

logger = logging.getLogger(__name__)


def dotted_chain(node: cst.BaseExpression) -> list[str] | None:
    """Return the root-first component list of a pure ``Name``/``Attribute`` chain.

    Args:
        node: The expression to inspect.

    Returns:
        The list of components (e.g. ``["foo", "bar"]`` for ``foo.bar``), or
        ``None`` if *node* is not a pure attribute chain rooted in a ``Name``
        (e.g. it contains a call or subscript).
    """
    parts: list[str] = []
    cur: cst.BaseExpression = node
    while isinstance(cur, cst.Attribute):
        parts.append(cur.attr.value)
        cur = cur.value
    if isinstance(cur, cst.Name):
        parts.append(cur.value)
        parts.reverse()
        return parts
    return None


def build_chain(parts: list[str]) -> cst.BaseExpression:
    """Build a ``Name``/``Attribute`` chain from root-first *parts*.

    Args:
        parts: The root-first component list.

    Returns:
        The corresponding CST expression.
    """
    node: cst.BaseExpression = cst.Name(parts[0])
    for part in parts[1:]:
        node = cst.Attribute(value=node, attr=cst.Name(part))
    return node


def target_names(node: cst.BaseExpression) -> set[str]:
    """Return the bare names bound by an assignment or ``for`` target."""
    if isinstance(node, cst.Name):
        return {node.value}
    if isinstance(node, cst.Tuple | cst.List):
        return {name for element in node.elements for name in target_names(element.value)}
    if isinstance(node, cst.StarredElement):
        return target_names(node.value)
    return set()


class LeakedBindingCollector(cst.CSTVisitor):
    """Collects the names a compound statement *leaks* into the enclosing scope.

    Where a collector of all block-bound names reports *every* name bound anywhere
    inside a block, this collector reports only the names that Python actually
    leaks out to the surrounding function scope once a ``for``/``with``/``if``/
    ``while``/``try`` block has executed:

    * ``with ... as`` targets,
    * ``for`` loop targets,
    * in-block assignments (``=``/``:=``/augmented/annotated), and
    * the *names* of nested ``def``/``class`` definitions.

    The names that stay block-local -- comprehension targets, ``lambda``
    parameters, and everything internal to a nested ``def``/``class`` body --
    are deliberately *not* collected, so a sibling block cannot wrongly resolve
    a reference against a name that does not exist at that point at runtime.
    """

    def __init__(self) -> None:  # noqa: D107
        self.bound: set[str] = set()

    @staticmethod
    def collect(node: cst.CSTNode) -> set[str]:
        """Collect the names leaked into the enclosing scope by *node*."""
        collector = LeakedBindingCollector()
        node.visit(collector)
        return collector.bound

    def _add_targets(self, node: cst.BaseExpression) -> None:
        self.bound.update(target_names(node))

    def visit_AssignTarget(self, node: cst.AssignTarget) -> bool:  # noqa: N802, D102
        self._add_targets(node.target)
        return True

    def visit_AnnAssign(self, node: cst.AnnAssign) -> bool:  # noqa: N802, D102
        self._add_targets(node.target)
        return True

    def visit_AugAssign(self, node: cst.AugAssign) -> bool:  # noqa: N802, D102
        self._add_targets(node.target)
        return True

    def visit_NamedExpr(self, node: cst.NamedExpr) -> bool:  # noqa: N802, D102
        self._add_targets(node.target)
        return True

    def visit_For(self, node: cst.For) -> bool:  # noqa: N802, D102
        self._add_targets(node.target)
        return True

    def visit_WithItem(self, node: cst.WithItem) -> bool:  # noqa: N802, D102
        # ``with ... as target`` leaks ``target``; an ``except ... as`` handler
        # (which uses a separate node) is deliberately not visited here because
        # Python deletes that binding at the end of the handler.
        if node.asname is not None:
            if isinstance(node.asname.name, cst.Name):
                self.bound.add(node.asname.name.value)
            else:
                self._add_targets(node.asname.name)
        return True

    def visit_FunctionDef(self, node: cst.FunctionDef) -> bool:  # noqa: N802, D102
        # The def *name* leaks into the enclosing scope; its parameters and body
        # stay local, so do not descend into it.
        self.bound.add(node.name.value)
        return False

    def visit_ClassDef(self, node: cst.ClassDef) -> bool:  # noqa: N802, D102
        # The class *name* leaks; its body stays local, so do not descend.
        self.bound.add(node.name.value)
        return False

    def visit_Lambda(self, node: cst.Lambda) -> bool:  # noqa: N802, D102
        # ``lambda`` parameters stay local to the lambda; do not descend.
        return False

    def visit_CompFor(self, node: cst.CompFor) -> bool:  # noqa: N802, D102
        # Comprehensions have their own scope, so their targets never leak.
        return False


def imported_local_names(node: cst.Import | cst.ImportFrom) -> list[str]:
    """Return the local (bound) names introduced by an import statement.

    Args:
        node: The import statement.

    Returns:
        The list of local names bound by the import.
    """
    names = node.names
    if isinstance(names, cst.ImportStar):
        return []
    result = []
    for alias in names:
        if alias.asname is not None and isinstance(alias.asname.name, cst.Name):
            result.append(alias.asname.name.value)
        elif isinstance(alias.name, cst.Name):
            result.append(alias.name.value)
        elif isinstance(alias.name, cst.Attribute):
            chain = dotted_chain(alias.name)
            if chain:
                result.append(chain[0])
    return result


class RelativeImportNormalizer(cst.CSTTransformer):
    """Normalizes relative ``ImportFrom`` statements to absolute imports."""

    def __init__(self, package_anchor: str) -> None:  # noqa: D107
        self._package_anchor = package_anchor

    def leave_ImportFrom(  # noqa: N802
        self, original_node: cst.ImportFrom, updated_node: cst.ImportFrom
    ) -> cst.ImportFrom:
        """Rewrite relative ImportFrom nodes to absolute ImportFrom nodes."""
        if not updated_node.relative or not self._package_anchor:
            return updated_node

        level_dots = "." * len(updated_node.relative)
        if updated_node.module is not None:
            dotted = dotted_chain(updated_node.module)
            if dotted is None:
                return updated_node
            rel_name = level_dots + ".".join(dotted)
        else:
            rel_name = level_dots

        try:
            abs_name = importlib.util.resolve_name(rel_name, self._package_anchor)
        except (ValueError, ImportError):
            logger.debug(
                "Could not resolve relative import %s with anchor %s",
                rel_name,
                self._package_anchor,
            )
            return updated_node

        abs_chain = abs_name.split(".")
        return updated_node.with_changes(
            relative=(),
            module=build_chain(abs_chain),
        )
