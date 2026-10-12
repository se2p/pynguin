#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Summarizes the call signatures of a module's public API for LLM prompts.

LLM-written tests often call the module under test with signatures that do not
match its API (missing required arguments, instantiating abstract classes), so
the tests fail on the clean module and are discarded.  The summary built here
lists, for every public class and function of the module, how to call it, so
prompts can state the API instead of leaving the model to guess it from the
(possibly truncated) source.
"""

from __future__ import annotations

import inspect
import sys
from typing import Any

#: Maximum number of methods listed per class.
_MAX_METHODS_PER_CLASS = 25

#: Default upper bound for the summary's length, in characters.
DEFAULT_MAX_CHARS = 8000


def _is_stdlib(obj: Any) -> bool:
    module_name = getattr(obj, "__module__", None) or "builtins"
    return module_name.split(".", maxsplit=1)[0] in sys.stdlib_module_names


def _signature(obj: Any) -> str:
    # Resolve string annotations (``from __future__ import annotations``) if possible.
    for eval_str in (True, False):
        try:
            signature = inspect.signature(obj, eval_str=eval_str)
        except Exception:  # noqa: BLE001, S112
            continue
        if inspect.isclass(obj):
            # A constructor returns an instance, not what ``__init__`` returns.
            signature = signature.replace(return_annotation=inspect.Signature.empty)
        return str(signature)
    return "(...)"


def _public_members(module: Any) -> list[tuple[str, Any]]:
    """Return the public classes and functions of *module*, its own ones first.

    Only the module's ``__dict__`` is read: ``getattr`` on a module that defines a
    module-level ``__getattr__`` could execute (instrumented) module code.
    """
    namespace = vars(module)
    exported = namespace.get("__all__")
    names = (
        [name for name in exported if isinstance(name, str)]
        if isinstance(exported, list | tuple)
        else [name for name in namespace if not name.startswith("_")]
    )
    members = [
        (name, namespace[name])
        for name in names
        if name in namespace
        and (inspect.isclass(namespace[name]) or inspect.isfunction(namespace[name]))
        and not _is_stdlib(namespace[name])
    ]
    module_name = getattr(module, "__name__", None)
    members.sort(key=lambda member: getattr(member[1], "__module__", None) != module_name)
    return members


def _method_lines(cls: type) -> list[str]:
    """Describe the public methods and properties of *cls* and its non-stdlib bases."""
    lines: list[str] = []
    seen: set[str] = set()
    for klass in cls.__mro__:
        if _is_stdlib(klass):
            continue
        for name, attr in vars(klass).items():
            if name.startswith("_") or name in seen:
                continue
            seen.add(name)
            if isinstance(attr, property):
                lines.append(f"    {name}  (property)")
            elif isinstance(attr, staticmethod):
                lines.append(f"    @staticmethod {name}{_signature(attr.__func__)}")
            elif isinstance(attr, classmethod):
                lines.append(f"    @classmethod {name}{_signature(getattr(cls, name))}")
            elif inspect.isfunction(attr):
                lines.append(f"    {name}{_signature(attr)}")
    if len(lines) > _MAX_METHODS_PER_CLASS:
        omitted = len(lines) - _MAX_METHODS_PER_CLASS
        lines = [*lines[:_MAX_METHODS_PER_CLASS], f"    ... ({omitted} more)"]
    return lines


def _abstract_note(cls: type, members: list[tuple[str, Any]]) -> str:
    abstract_methods = ", ".join(sorted(getattr(cls, "__abstractmethods__", ())))
    concrete = [
        name
        for name, obj in members
        if inspect.isclass(obj)
        and obj is not cls
        and issubclass(obj, cls)
        and not inspect.isabstract(obj)
    ]
    note = f"  # ABSTRACT (abstract methods: {abstract_methods}); never instantiate it directly"
    if concrete:
        note += "; instantiate a concrete subclass instead: " + ", ".join(concrete)
    return note


def _describe_class(name: str, cls: type, members: list[tuple[str, Any]], *, own: bool) -> str:
    header = f"class {name}{_signature(cls)}"
    if inspect.isabstract(cls):
        header += _abstract_note(cls, members)
    if not own:
        # Imported classes only get their constructor, to bound the summary.
        return header
    return "\n".join([header, *_method_lines(cls)])


def describe_module_api(module: Any, max_chars: int | None = DEFAULT_MAX_CHARS) -> str:
    """Summarize how to call the public classes and functions of *module*.

    Classes are listed with their constructor signature (without ``self``) and,
    for classes defined in the module, their public methods and properties.
    Abstract classes are marked, with the concrete subclasses the module offers.

    Args:
        module: The module under test.
        max_chars: Upper bound for the summary's length; entries that do not fit
            are left out.  ``None`` or a value <= 0 disables the bound.

    Returns:
        The summary, or ``""`` if the module has no public classes or functions.
    """
    try:
        members = _public_members(module)
    except Exception:  # noqa: BLE001
        return ""
    module_name = getattr(module, "__name__", None)
    entries: list[str] = []
    size = 0
    for name, obj in members:
        try:
            if inspect.isclass(obj):
                own = obj.__module__ == module_name
                entry = _describe_class(name, obj, members, own=own)
            else:
                entry = f"def {name}{_signature(obj)}"
        except Exception:  # noqa: BLE001, S112
            continue
        if max_chars and max_chars > 0 and size + len(entry) + 1 > max_chars:
            break
        entries.append(entry)
        size += len(entry) + 1
    return "\n".join(entries)
