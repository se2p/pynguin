#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Finds the boundary classes reachable only through untyped parameters.

Statically collects the attributes accessed on each untyped parameter and matches
them against the classes Pynguin can generate, so those candidates can be
classified up front without proxy-cache calls and without relying on parameter
names. Both direct attribute access and constructor parameters stored on ``self``
are handled.
"""

from __future__ import annotations

import ast

from pynguin.mock_generation.ast_helpers import param_names

# Attributes on scalar/text primitives. A param accessing only these is a
# primitive value, not a boundary (containers excluded: names overlap domain).
_PRIMITIVE_ATTRS: frozenset[str] = frozenset().union(
    *(dir(t) for t in (str, bytes, int, float, complex, bool))
)


def _is_primitive_signature(attrs: set[str]) -> bool:
    """True when every accessed attribute belongs to a scalar/text primitive type."""
    return bool(attrs) and attrs <= _PRIMITIVE_ATTRS


def untyped_param_bindings(source: str) -> dict[tuple[str, str], set[str]]:
    """Return ``(callable_qualname, param_name) -> attribute set`` for untyped params.

    *callable_qualname* matches the callable's runtime ``__qualname__``, so the
    test factory can inject a mock for a specific untyped parameter. Bindings with
    an empty or primitive-only attribute set are omitted.
    """
    tree = ast.parse(source)
    out: dict[tuple[str, str], set[str]] = {}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            _add_function_bindings(node, node.name, out)
        elif isinstance(node, ast.ClassDef):
            _add_class_bindings(node, out)
    return {
        key: attrs for key, attrs in out.items() if attrs and not _is_primitive_signature(attrs)
    }


def untyped_param_attr_sets(source: str) -> list[set[str]]:
    """Return one attribute set per untyped parameter that is used as an object.

    source: the module's Python source. Each returned set holds the attribute
    names accessed on a single untyped parameter; empty sets are omitted.
    """
    return [attrs for attrs in untyped_param_bindings(source).values() if attrs]


def match_param_boundaries(
    bindings: dict[tuple[str, str], set[str]], classes: list[type]
) -> dict[tuple[str, str], str]:
    """Map ``(callable_qualname, param) -> class FQN`` for each unambiguous binding.

    bindings: from untyped_param_bindings. classes: candidate boundary classes.
    A class satisfies a binding when it has every attribute in the binding's set.
    A parameter is bound only when exactly one candidate class satisfies it, so
    weak matches (a common attribute shared by several classes) do not over-mock.
    """
    matched: dict[tuple[str, str], str] = {}
    for key, attrs in bindings.items():
        if not attrs:
            continue
        hits = [
            f"{getattr(cls, '__module__', '') or ''}.{getattr(cls, '__name__', '')}"
            for cls in classes
            if all(_safe_hasattr(cls, a) for a in attrs)
        ]
        # Bind only on an unambiguous single match to avoid over-mocking
        if len(hits) == 1:
            matched[key] = hits[0]
    return matched


def match_candidate_classes(attr_sets: list[set[str]], classes: list[type]) -> dict[str, type]:
    """Map FQN -> class for every class that satisfies at least one attribute set.

    attr_sets: attribute sets from untyped_param_attr_sets. classes: the classes
    Pynguin can generate (from the test cluster). A class matches a set when it
    has every attribute in that set.
    """
    matched: dict[str, type] = {}
    for cls in classes:
        for attrs in attr_sets:
            if attrs and all(_safe_hasattr(cls, a) for a in attrs):
                mod = getattr(cls, "__module__", "") or ""
                matched[f"{mod}.{getattr(cls, '__name__', '')}"] = cls
                break
    return matched


def _safe_hasattr(cls: type, attr: str) -> bool:
    try:
        return hasattr(cls, attr)
    except Exception:  # noqa: BLE001
        return False


def _direct_attr_accesses(node: ast.AST, names: set[str]) -> dict[str, set[str]]:
    """Attributes accessed as ``<name>.<attr>`` for each name in *names*."""
    out: dict[str, set[str]] = {}
    for child in ast.walk(node):
        if (
            isinstance(child, ast.Attribute)
            and isinstance(child.value, ast.Name)
            and child.value.id in names
        ):
            out.setdefault(child.value.id, set()).add(child.attr)
    return out


def _add_function_bindings(
    func: ast.FunctionDef | ast.AsyncFunctionDef,
    qualname: str,
    out: dict[tuple[str, str], set[str]],
) -> None:
    """Record ``(qualname, param) -> attrs`` for untyped params used directly."""
    untyped = param_names(func, untyped_only=True)
    if not untyped:
        return
    direct = _direct_attr_accesses(func, untyped)
    for name in untyped:
        if name in direct:
            out.setdefault((qualname, name), set()).update(direct[name])


def _self_param_bindings(
    init: ast.FunctionDef | ast.AsyncFunctionDef, untyped: set[str]
) -> dict[str, str]:
    """Map ``self.x`` attribute name -> parameter for ``self.x = param`` assignments."""
    bindings: dict[str, str] = {}
    for node in ast.walk(init):
        if (
            isinstance(node, ast.Assign)
            and isinstance(node.value, ast.Name)
            and node.value.id in untyped
        ):
            for target in node.targets:
                if (
                    isinstance(target, ast.Attribute)
                    and isinstance(target.value, ast.Name)
                    and target.value.id == "self"
                ):
                    bindings[target.attr] = node.value.id
    return bindings


def _self_attr_accesses(node: ast.AST) -> dict[str, set[str]]:
    """Attributes accessed as ``self.<x>.<attr>``, mapping x -> {attr}."""
    out: dict[str, set[str]] = {}
    for child in ast.walk(node):
        if (
            isinstance(child, ast.Attribute)
            and isinstance(child.value, ast.Attribute)
            and isinstance(child.value.value, ast.Name)
            and child.value.value.id == "self"
        ):
            out.setdefault(child.value.attr, set()).add(child.attr)
    return out


def _add_class_bindings(cls: ast.ClassDef, out: dict[tuple[str, str], set[str]]) -> None:
    """Record untyped-param bindings for a class's methods and constructor."""
    methods = [n for n in cls.body if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)]

    # Untyped parameters used directly inside their own method (qualname "C.m").
    for method in methods:
        _add_function_bindings(method, f"{cls.name}.{method.name}", out)

    # Constructor parameters stored on self and used across the class's methods;
    # attributed to the constructor (qualname "C.__init__").
    init = next((m for m in methods if m.name == "__init__"), None)
    if init is not None:
        bindings = _self_param_bindings(init, param_names(init, untyped_only=True))
        if bindings:
            self_attrs: dict[str, set[str]] = {}
            for method in methods:
                for attr, names in _self_attr_accesses(method).items():
                    self_attrs.setdefault(attr, set()).update(names)
            for self_attr, param in bindings.items():
                attrs = self_attrs.get(self_attr)
                if attrs:
                    out.setdefault((f"{cls.name}.__init__", param), set()).update(attrs)
