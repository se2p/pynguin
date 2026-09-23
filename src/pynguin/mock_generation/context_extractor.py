#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Extracts a function's usage context from its AST for mock generation.

Records how tracked dependencies are used inside each function so the LLM can
generate focused mock configurations. The analysis is shallow. Only the direct
body of each function is gathered, control flow and nested definitions ignored.
"""

from __future__ import annotations

import ast
import inspect
import logging
import textwrap
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from pynguin.mock_generation.ast_helpers import import_alias_map

if TYPE_CHECKING:
    from pathlib import Path

_logger = logging.getLogger(__name__)


# Data structures


@dataclass
class MethodCall:
    """A method invoked directly on a tracked dependency variable."""

    method_name: str
    args_count: int
    has_kwargs: bool


@dataclass
class AttributeAccess:
    """An attribute or method accessed on the return value of a dependency call."""

    attribute_name: str
    is_method_call: bool


@dataclass
class DependencyUsage:
    """Usage context for a single dependency within a function."""

    dependency: str
    variable_names: list[str] = field(default_factory=list)
    method_calls: list[MethodCall] = field(default_factory=list)
    return_value_accesses: list[AttributeAccess] = field(default_factory=list)


@dataclass
class FunctionContext:
    """Extracted usage context for a single function."""

    function_name: str
    source_code: str
    dependencies: list[DependencyUsage] = field(default_factory=list)


# Extractor


class ContextExtractor:
    """Extracts dependency usage context from Python source code via AST analysis.

    Args:
        dependencies: Top-level dependency names to track, typically the
            libraries returned by
            :class:`~pynguin.mock_generation.dependency_analyzer.DependencyAnalyzer`
            with ``decision="mock"``.
    """

    def __init__(self, dependencies: list[str]) -> None:
        """Initialise with the list of dependency names to track."""
        self._dependencies: frozenset[str] = frozenset(dependencies)

    # Public API

    def extract_from_file(self, path: Path) -> list[FunctionContext]:
        """Extract usage context from all functions in a Python file.

        Args:
            path: Path to a Python module file.

        Returns:
            One :class:`FunctionContext` per function that uses at least one
            tracked dependency, in source order.

        Raises:
            OSError: If *path* cannot be read.
            SyntaxError: If the source is not valid Python.
        """
        source = path.read_text(encoding="utf-8")
        return self.extract_from_source(source)

    def extract_from_source(self, source: str) -> list[FunctionContext]:
        """Extract usage context from a source code string.

        Args:
            source: Python source code.

        Returns:
            One :class:`FunctionContext` per function that uses at least one
            tracked dependency, in source order.

        Raises:
            SyntaxError: If *source* is not valid Python.
        """
        tree = ast.parse(source)
        alias_map = self._build_import_alias_map(tree)
        contexts: list[FunctionContext] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                ctx = self.extract_from_function(node, source, alias_map)
                if ctx is not None:
                    contexts.append(ctx)
        _logger.debug("Extracted context from %d function(s)", len(contexts))
        return contexts

    def extract_from_function(
        self,
        func_node: ast.FunctionDef | ast.AsyncFunctionDef,
        source: str,
        alias_map: dict[str, str] | None = None,
    ) -> FunctionContext | None:
        """Extract usage context from a single function AST node.

        Args:
            func_node: AST node for the function definition.
            source: Full module source (used to slice out the function text).
            alias_map: Local-name → dependency map from
                :meth:`_build_import_alias_map`.  Pass ``None`` when calling
                outside of :meth:`extract_from_source`.

        Returns:
            :class:`FunctionContext` when the function uses at least one
            tracked dependency, ``None`` otherwise.
        """
        dep_vars, return_vars = self._find_dependency_variables(func_node, alias_map or {})
        if not dep_vars:
            return None

        method_calls = self._extract_method_calls(func_node, dep_vars)
        return_accesses = self._extract_return_value_accesses(func_node, return_vars)

        # Collect usages, only include deps that have at least one observed usage.
        usages: list[DependencyUsage] = []
        for dep_name in self._dependencies:
            calls = method_calls.get(dep_name, [])
            accesses = return_accesses.get(dep_name, [])
            if not calls and not accesses:
                continue
            var_names = [v for v, d in dep_vars.items() if d == dep_name]
            usages.append(
                DependencyUsage(
                    dependency=dep_name,
                    variable_names=var_names,
                    method_calls=calls,
                    return_value_accesses=accesses,
                )
            )

        if not usages:
            return None

        func_source = self._slice_function_source(func_node, source)
        return FunctionContext(
            function_name=func_node.name,
            source_code=func_source,
            dependencies=usages,
        )

    # Variable tracking

    def _find_dependency_variables(
        self,
        func_node: ast.FunctionDef | ast.AsyncFunctionDef,
        alias_map: dict[str, str],
    ) -> tuple[dict[str, str], dict[str, str]]:
        """Map variable names to their source dependency within *func_node*.

        Returns two dicts. *dep_vars* holds variables that are the dependency or
        a direct alias, seeded from function parameters, direct dependency
        references in the body, and names imported from a tracked dependency.
        *return_vars* holds variables assigned from a dependency call.

        Args:
            func_node: Function AST node to inspect.
            alias_map: ``{imported_name: top_level_package}`` from
                :meth:`_build_import_alias_map`.

        Returns:
            Tuple of ``(dep_vars, return_vars)``.
        """
        dep_vars: dict[str, str] = {}
        return_vars: dict[str, str] = {}

        # Parameters whose name is a tracked dependency
        for arg in func_node.args.args + func_node.args.posonlyargs + func_node.args.kwonlyargs:
            if arg.arg in self._dependencies:
                dep_vars[arg.arg] = arg.arg

        # Names in the body that are a direct dependency reference or an import alias
        for node in self._walk_body(func_node):
            if not isinstance(node, ast.Name):
                continue
            name = node.id
            if name in dep_vars:
                continue
            if name in self._dependencies:
                dep_vars[name] = name
            elif name in alias_map:
                dep_vars[name] = alias_map[name]

        for stmt in func_node.body:
            self._process_assignment(stmt, dep_vars, return_vars)

        return dep_vars, return_vars

    def _process_assignment(
        self,
        stmt: ast.stmt,
        dep_vars: dict[str, str],
        return_vars: dict[str, str],
    ) -> None:
        """Update *dep_vars* / *return_vars* for a single assignment statement."""
        targets: list[ast.Name] = []
        value: ast.expr | None = None

        if isinstance(stmt, ast.Assign):
            value = stmt.value
            targets = [t for t in stmt.targets if isinstance(t, ast.Name)]
        elif isinstance(stmt, ast.AnnAssign) and stmt.value is not None:
            value = stmt.value
            if isinstance(stmt.target, ast.Name):
                targets = [stmt.target]

        if value is None or not targets:
            return

        direct = self._alias_dep(value, dep_vars)
        if direct is not None:
            for t in targets:
                dep_vars[t.id] = direct
            return

        via_call = self._call_dep(value, dep_vars)
        if via_call is not None:
            for t in targets:
                return_vars[t.id] = via_call

    def _alias_dep(self, expr: ast.expr, dep_vars: dict[str, str]) -> str | None:
        """Return dep name if *expr* is a direct name reference to a dep var."""
        if isinstance(expr, ast.Name) and expr.id in dep_vars:
            return dep_vars[expr.id]
        return None

    def _call_dep(self, expr: ast.expr, dep_vars: dict[str, str]) -> str | None:
        """Return dep name if *expr* is (ultimately) a call on a dep var."""
        if isinstance(expr, ast.Call):
            return self._call_dep(expr.func, dep_vars)
        if isinstance(expr, ast.Attribute):
            return self._call_dep(expr.value, dep_vars)
        if isinstance(expr, ast.Name) and expr.id in dep_vars:
            return dep_vars[expr.id]
        return None

    # Method call extraction

    def _extract_method_calls(
        self,
        func_node: ast.FunctionDef | ast.AsyncFunctionDef,
        dep_vars: dict[str, str],
    ) -> dict[str, list[MethodCall]]:
        """Extract method calls made directly on tracked dependency variables.

        Args:
            func_node: Function AST node.
            dep_vars: Direct dependency variable mapping.

        Returns:
            ``{dependency_name: [MethodCall, ...]}``
        """
        result: dict[str, list[MethodCall]] = {}

        for node in self._walk_body(func_node):
            if not isinstance(node, ast.Call):
                continue
            func = node.func

            if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
                var_name = func.value.id
                if var_name in dep_vars:
                    call = MethodCall(
                        method_name=func.attr,
                        args_count=len(node.args),
                        has_kwargs=bool(node.keywords),
                    )
                    result.setdefault(dep_vars[var_name], []).append(call)

            elif isinstance(func, ast.Name) and func.id in dep_vars:
                call = MethodCall(
                    method_name=func.id,
                    args_count=len(node.args),
                    has_kwargs=bool(node.keywords),
                )
                result.setdefault(dep_vars[func.id], []).append(call)

        return result

    # Return-value attribute extraction

    def _extract_return_value_accesses(
        self,
        func_node: ast.FunctionDef | ast.AsyncFunctionDef,
        return_vars: dict[str, str],
    ) -> dict[str, list[AttributeAccess]]:
        """Extract attribute / method accesses on return values of dependencies.

        Args:
            func_node: Function AST node.
            return_vars: Return-value variable → dependency mapping.

        Returns:
            ``{dependency_name: [AttributeAccess, ...]}``
        """
        result: dict[str, list[AttributeAccess]] = {}

        for node in self._walk_body(func_node):
            attr_node: ast.Attribute | None = None
            is_call = False

            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                attr_node = node.func
                is_call = True
            elif isinstance(node, ast.Attribute):
                attr_node = node
                is_call = False

            if attr_node is None:
                continue
            if not isinstance(attr_node.value, ast.Name):
                continue
            var_name = attr_node.value.id
            if var_name not in return_vars:
                continue

            dep = return_vars[var_name]
            access = AttributeAccess(attribute_name=attr_node.attr, is_method_call=is_call)
            result.setdefault(dep, []).append(access)

        return result

    # Helpers

    def _build_import_alias_map(self, tree: ast.Module) -> dict[str, str]:
        """Build ``{local_name: top_level_package}`` for tracked dependencies only.

        Args:
            tree: Parsed AST of the full module.

        Returns:
            Mapping of local name to tracked top-level dependency package.
        """
        result: dict[str, str] = {}
        for local_name, dotted in import_alias_map(tree).items():
            pkg = dotted.split(".", 1)[0]
            if pkg in self._dependencies:
                result[local_name] = pkg
        return result

    @staticmethod
    def _walk_body(
        func_node: ast.FunctionDef | ast.AsyncFunctionDef,
    ):
        """Yield all AST nodes reachable from *func_node*'s direct body.

        Uses an explicit queue (BFS) so that nested ``FunctionDef``,
        ``AsyncFunctionDef``, and ``ClassDef`` nodes can be yielded but
        never descended into, keeping analysis at a single level.
        """
        queue: list[ast.AST] = list(func_node.body)
        while queue:
            node = queue.pop(0)
            yield node
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
                queue.extend(ast.iter_child_nodes(node))

    @staticmethod
    def _slice_function_source(
        func_node: ast.FunctionDef | ast.AsyncFunctionDef,
        source: str,
    ) -> str:
        """Return the original source text for *func_node*.

        Falls back to ``ast.unparse`` if line info is unavailable.

        Args:
            func_node: Function AST node (must have ``lineno`` set).
            source: Full module source string.

        Returns:
            Dedented source text of the function.
        """
        try:
            lines = source.splitlines(keepends=True)
            start = func_node.lineno - 1
            end = func_node.end_lineno or len(lines)
            return textwrap.dedent("".join(lines[start:end]))
        except AttributeError:
            return inspect.cleandoc(ast.unparse(func_node))
