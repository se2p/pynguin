# This file is part of the Pynguin automated unit test generation framework.
# Copyright (C) 2019–2026 Pynguin Contributors
# SPDX-License-Identifier: MIT
#
"""Provides utilities for naming things in the generated code."""

from __future__ import annotations

import importlib.util
from pathlib import Path


def get_module_alias(module_name: str) -> str:
    """Return the alias used for the module under test.

    Appends a trailing underscore to avoid name collisions with package members.

    Args:
        module_name: The name of the module under test.

    Returns:
        The alias to use in generated code.
    """
    return module_name.rsplit(".", 1)[-1] + "_"


def dotted_module_path_from_origin(origin: str) -> str | None:
    """Return the dotted module path derived from ``spec.origin``.

    Check the parent directory for __init__.py until none is found. Then get the path
    based on the first __init__.py found.

    Args:
        origin: The origin of the module spec.

    Returns:
        The dotted module path or None if the origin is not a file.
    """
    if not origin or origin in {"built-in", "frozen"}:
        return None

    module = Path(origin)
    if not module.is_file():
        return None

    # Walk upward while parent contains __init__.py
    module_root = module
    while (module_root.parent / "__init__.py").exists():
        module_root = module_root.parent

    if module_root.parent is None:
        return None

    rel = module.relative_to(module_root.parent)

    # If the resolved origin points to a package's __init__.py, use the directory
    # name as the canonical module path (e.g., pathlib/__init__.py -> pathlib).
    if rel.name == "__init__.py":
        rel = rel.parent
        return ".".join(rel.parts)

    # For compiled extensions get the clean module name
    stem = rel.stem
    if "." in stem and rel.suffix in {".so", ".pyd", ".dll"}:
        # Take only the first part before any dots in the stem
        # e.g., "array.cpython-310-darwin" -> "array"
        stem = stem.split(".")[0]
        if rel.parent == Path():
            return stem
    return ".".join([*rel.parent.parts, stem])


def _resolves_to_same_origin(dotted: str, origin: str) -> bool:
    """Check whether importing ``dotted`` resolves to the file at ``origin``.

    Args:
        dotted: The candidate dotted module name.
        origin: The origin (file path) the name must resolve to.

    Returns:
        True iff ``dotted`` is importable and points to the same file as ``origin``.
    """
    try:
        other = importlib.util.find_spec(dotted)
    except (ImportError, AttributeError, ValueError):
        return False
    other_origin = getattr(other, "origin", None)
    if not other_origin:
        return False
    return Path(other_origin).resolve() == Path(origin).resolve()


def canonical_module_name(name: str) -> str:
    """Return a fully qualified module name for use in import statements.

    Strategy:
    1) Try ``importlib.util.find_spec(name)`` and derive from ``spec.origin`` -- but
       only trust that origin-derived name when it actually imports back to the same
       file. The filesystem derivation climbs while ``__init__.py`` files exist, which
       drops a leading PEP 420 namespace-package segment (a directory without an
       ``__init__.py`` that is nonetheless importable, e.g. ``google`` in
       ``google.auth._helpers``); the resulting ``auth._helpers`` would emit an
       unimportable ``import auth._helpers``. Stripping a genuinely non-canonical
       prefix such as ``src`` is kept because the shortened name still resolves.
    2) Fall back to ``spec.name`` if available.
    3) Otherwise, return ``name`` unchanged.

    Args:
        name: The module name.

    Returns:
        The fully qualified module name.
    """
    try:
        spec = importlib.util.find_spec(name)
    except Exception:  # noqa: BLE001
        spec = None

    if spec and getattr(spec, "origin", None):
        dotted = dotted_module_path_from_origin(spec.origin)  # type: ignore[arg-type]
        if dotted and _resolves_to_same_origin(dotted, spec.origin):  # type: ignore[arg-type]
            return dotted
    if spec and getattr(spec, "name", None):
        return spec.name

    return name
