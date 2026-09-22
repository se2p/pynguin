#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Small AST helpers shared across the mock-generation analysers."""

from __future__ import annotations

import ast


def import_alias_map(tree: ast.Module) -> dict[str, str]:
    """Map each imported name to the full dotted path it refers to.

    Args:
        tree: Parsed AST of the module.

    Returns:
        Mapping of local name to its fully-qualified dotted path.
    """
    out: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                out[alias.asname or alias.name.split(".")[0]] = alias.name
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            for alias in node.names:
                out[alias.asname or alias.name] = f"{node.module}.{alias.name}"
    return out


def param_names(
    func: ast.FunctionDef | ast.AsyncFunctionDef, *, untyped_only: bool = False
) -> set[str]:
    """Names of a function's parameters, excluding ``self``/``cls``.

    Args:
        func: The function AST node.
        untyped_only: When True, keep only parameters with no annotation.

    Returns:
        The set of parameter names.
    """
    args = func.args
    return {
        arg.arg
        for arg in (*args.posonlyargs, *args.args, *args.kwonlyargs)
        if arg.arg not in {"self", "cls"} and (not untyped_only or arg.annotation is None)
    }
