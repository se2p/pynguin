#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2024 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides class prompt for type inference using LLMs."""

import inspect
import textwrap
from collections.abc import Callable
from typing import Any

from pynguin.utils.orderedset import OrderedSet

_ROLE_USER = "<|user|>"


class TypeInferencePrompt:
    """Implementation prompt for type inference using LLMs."""

    # TODO: load templates form src/pynguin/resources/ would be cleaner
    def __init__(
        self, callable_obj: Callable[..., Any], subtypes: OrderedSet[str] | None = None
    ) -> None:
        """Creates a new TypeInferencePrompt.

        Args:
            callable_obj: the callable object for which types should be inferred
            subtypes: list of known string subtypes (e.g., "email", "url", etc.)
        """
        self.callable_obj = callable_obj
        self.subtypes: OrderedSet[str] = subtypes or []  # type: ignore[assignment]

    def build_user_prompt(self) -> str:
        """Build the complete prompt for type inference."""
        template = textwrap.dedent(
            """
            You are tasked with inferring parameter types for a given Python function.

            ## Module Context
            - Imports in the module:
            {imports}

            - Parent class name:
            {parent_class}

            - All classes in the same module:
            {all_classes}

            - Known string subtypes:
            {subtype_list}

            ## Target Function
            - Function signature:
            {signature}

            - Docstring:
            {docstring}

            - Function body:
            {body}

            ## Additional Context
            - Other function signatures in the same class:
            {other_functions}

            ## Task
            Infer the parameter types for the target function above.

            Return your answer **only** as JSON in the following format:
            {{
                "param1": <qualname of type>,
                "param2": <qualname of type>
            }}
            """
        ).lstrip()

        formatted_template = template.format(
            parent_class=self._get_parent_class_name(self.callable_obj),
            imports=self._get_imports(self.callable_obj),
            all_classes=self._get_all_classes_in_module(),
            other_functions=self._get_all_function_signatures_in_class(self.callable_obj),
            signature=self._get_signature_str(self.callable_obj),
            docstring=self._get_docstring(self.callable_obj),
            body=self._get_src_code(self.callable_obj),
            subtype_list=self._get_str_subtypes(),
        )
        return f"{formatted_template}"

    def _get_src_code(self, func: Callable[..., Any]) -> str:
        try:
            return inspect.getsource(func)
        except (OSError, TypeError):
            name = getattr(func, "__qualname__", getattr(func, "__name__", "<callable>"))
            sig = self._get_signature_str(func)
            return f"def {name}{sig}:\n    pass\n"

    @staticmethod
    def _get_signature_str(func: Callable[..., Any]) -> str:
        try:
            sig = inspect.signature(func)
            return str(sig)
        except (TypeError, ValueError):
            return "( *args, **kwargs )"

    @staticmethod
    def _get_docstring(func: Callable[..., Any]) -> str:
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
        qualname = getattr(func, "__qualname__", "")
        parts = qualname.split(".")
        if len(parts) > 1:
            return parts[-2]
        return "No parent class"

    def _get_all_classes_in_module(self) -> str:
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
        return ", ".join(list(self.subtypes)) if self.subtypes else "(none)"


def get_inference_system_prompt() -> str:
    """Build the system prompt for type inference."""
    return textwrap.dedent(
        """
            You are a Python type inference engine.
            Your task is to analyze given Python functions and infer the parameter types.
            Think step by step. Before inferring types, analyze the given context.
            Reason about each parameter's type based on usage and context.
            Keep this reasoning to yourself and do not include it in the final output.
            Use your knowledge of programming, common libraries, and best practices to infer types.
            Use the provided context to make an informed decision about the types of parameters.
            Always return results in full qualified names, e.g., typing.List[builtins.int].
            *NEVER* use Any or object as a type.
            Only infer types for parameters, exclude self and return types.
            Return your output in JSON format only.

            When a parameter is a string, consider if it matches one of the known
            string subtypes and prefer returning that subtype when appropriate.
            """
    ).strip()
