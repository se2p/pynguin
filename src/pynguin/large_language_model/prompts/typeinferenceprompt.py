#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2024 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides class prompt for type inference using LLMs."""

import datetime
import inspect
import textwrap
from collections.abc import Callable
from typing import Any


_ROLE_USER = "<|user|>"


class TypeInferencePrompt:
    """Implementation prompt for type inference using LLMs."""

    def __init__(self, callable_obj: Callable[..., Any]):
        """Creates a new TypeInferencePrompt.

        Args:
            module_code: the module code to be passed to the prompt
            module_path: the module file path
            callable_obj: the callable object for which types should be inferred
        """
        self.callable_obj = callable_obj

    def build_user_prompt(self) -> str:
        """Build the complete prompt for type inference."""
        template = textwrap.dedent(
            """
            Use this context to infer parameter types for the given function.

            This is the name of the parent class:
            {parent_class}

            This is a list of all classes in the same module:
            {all_classes}

            Function signature:
            {signature}

            Infer the parameter types for the following Python function.

            Docstring:
            {docstring}

            Function body:
            {body}

            These are all function signatures in the same class:
            {other_functions}

            Return your answer as JSON in the following format:
            {{
                    "param1": "Type",
                    "param2": "Type"
            }}
            """
        ).lstrip()

        formatted_template = template.format(
            parent_class=self._get_parent_class_name(self.callable_obj),
            all_classes=self._get_all_classes_in_module(),
            other_functions=self._get_all_function_signatures_in_class(self.callable_obj),
            signature=self._get_signature_str(self.callable_obj),
            docstring=self._get_docstring(self.callable_obj),
            body=self._get_src_code(self.callable_obj),
        )
        return f"{formatted_template}"

    def _get_src_code(self, func: Callable[..., Any]) -> str:
        try:
            return inspect.getsource(func)
        except (OSError, TypeError):
            name = getattr(func, "__qualname__", getattr(func, "__name__", "<callable>"))
            sig = self._safe_signature_str(func)
            return f"def {name}{sig}:\n    pass\n"

    def _safe_signature_str(self, func: Callable[..., Any]) -> str:
        try:
            sig = inspect.signature(func)
            return str(sig)
        except (TypeError, ValueError):
            return "( *args, **kwargs )"

    def _get_signature_str(self, func: Callable[..., Any]) -> str:
        try:
            sig = inspect.signature(func)
            return str(sig)
        except (TypeError, ValueError):
            return "( *args, **kwargs )"

    def _get_docstring(self, func: Callable[..., Any]) -> str:
        return inspect.getdoc(func) or "No docstring available."

    def _get_all_function_signatures_in_class(self, func: Callable[..., Any]) -> str:
        """Return a comma-separated list of all function signatures in the same class as the given function."""
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
            if member is func:  # skip the function we started from
                continue
            try:
                sig = str(inspect.signature(member))
            except (TypeError, ValueError):
                sig = "(...)"  # fallback if signature inspection fails
            signatures.append(f"{name}{sig}")

        return ", ".join(signatures)

    def _get_parent_class_name(self, func: Callable[..., Any]) -> str:
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
def get_inference_system_prompt() -> str:
    """Build the system prompt for type inference."""
    guidelines = textwrap.dedent(
        """
            You are a Python type inference engine.
            Your task is to analyze given Python functions and infer the most accurate parameter types.
            Use your knowledge of programming, common libraries, and best practices to deduce types.
            Use the provided context to make an informed decision about the types of parameters.
            - Always return results in valid Python type annotation syntax (PEP 484).
            - Any type should be avoided as inference unless absolutely necessary.
            - only infer types for parameters, exclude self and return types.
            - For string parameters, also infer subtypes if applicable:
              - NumericString
              - DelimitedString
              - XMLString
            Return your output in JSON format only.

            """
    ).strip()
    today = datetime.datetime.now(tz=datetime.timezone.utc).date().isoformat()
    header = f"<|system|>\n## Analysis Instructions ({today})"
    return f"{header}\n{guidelines}"
