#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2024 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides base class for type inference prompts using LLMs."""

import inspect
from collections.abc import Callable
from typing import Any

from pynguin.utils.orderedset import OrderedSet


class BaseInferencePrompt:
    """Base class for type inference prompts."""

    def __init__(
        self, callable_obj: Callable[..., Any], subtypes: OrderedSet[str] | None = None
    ) -> None:
        """Creates a new BaseInferencePrompt.

        Args:
            callable_obj: the callable object for which types should be inferred
            subtypes: list of known string subtypes (e.g., "email", "url", etc.)
        """
        self.callable_obj = callable_obj
        self.subtypes: OrderedSet[str] = subtypes or []  # type: ignore[assignment]

    def _get_src_code(self, func: Callable[..., Any]) -> str:
        """Get the source code of a function."""
        try:
            return inspect.getsource(func)
        except (OSError, TypeError):
            name = getattr(func, "__qualname__", getattr(func, "__name__", "<callable>"))
            sig = self._get_signature_str(func)
            return f"def {name}{sig}:\n    pass\n"

    @staticmethod
    def _get_signature_str(func: Callable[..., Any]) -> str:
        """Get the signature string of a function."""
        try:
            sig = inspect.signature(func)
            return str(sig)
        except (TypeError, ValueError):
            return "( *args, **kwargs )"

    @staticmethod
    def _get_docstring(func: Callable[..., Any]) -> str:
        """Get the docstring of a function."""
        return inspect.getdoc(func) or "No docstring available."

    @staticmethod
    def _get_all_function_signatures_in_class(func: Callable[..., Any]) -> str:
        """Return a comma-separated list of all function signatures in the same class as func."""
        cls = getattr(func, "__qualname__", "").split(".<locals>", 1)[0].rsplit(".", 1)
        if len(cls) < 2:
            return ""
        cls_name = cls[0]
        module = inspect.getmodule(func)
        if module is None or not hasattr(module, cls_name):
            return ""
        cls_obj = getattr(module, cls_name)
        if not inspect.isclass(cls_obj):
            return ""

        signatures = []
        for name, member in inspect.getmembers(cls_obj, predicate=inspect.isfunction):
            if member is func:
                continue
            try:
                sig = str(inspect.signature(member))
            except (TypeError, ValueError):
                sig = "(...)"
            signatures.append(f"{name}{sig}")

        return ", ".join(signatures)

    @staticmethod
    def _get_parent_class_name(func: Callable[..., Any]) -> str:
        """Get the parent class name of a function."""
        qualname = getattr(func, "__qualname__", "")
        parts = qualname.split(".")
        if len(parts) > 1:
            return parts[-2]
        return "No parent class"

    def _get_all_classes_in_module(self) -> str:
        """Get all classes in the module of the callable object."""
        module = inspect.getmodule(self.callable_obj)
        if module is None:
            return "No module found."

        def collect_classes(obj, prefix=""):
            class_list = []
            for name, cls in inspect.getmembers(obj, predicate=inspect.isclass):
                if cls.__module__ != module.__name__:
                    continue
                full_name = f"{prefix}{name}" if not prefix else f"{prefix}.{name}"
                class_list.append(full_name)
                class_list.extend(collect_classes(cls, prefix=full_name))
            return class_list

        all_classes = collect_classes(module)

        return ", ".join(all_classes) if all_classes else "No classes found."

    @staticmethod
    def _get_imports(func: Callable[..., Any]) -> str:
        """Get the import statements from the module of a function."""
        module = inspect.getmodule(func)
        if module is None:
            return "no imports found"
        try:
            source = inspect.getsource(module)
        except (OSError, TypeError):
            return "there was an error retrieving the imports"
        import_lines = [
            line for line in source.splitlines() if line.startswith(("import ", "from "))
        ]
        return "\n".join(import_lines)

    def _get_str_subtypes(self) -> str:
        """Get the string subtypes as a formatted string."""
        return ", ".join(list(self.subtypes)) if self.subtypes else "(none)"
