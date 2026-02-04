#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides enhanced prompt for type and subtype inference using LLMs."""

import textwrap
from collections.abc import Callable
from typing import Any

from pynguin.large_language_model.prompts.base_inference_prompt import BaseInferencePrompt
from pynguin.utils.orderedset import OrderedSet

_ROLE_USER = "<|user|>"


class TypeAndSubtypeInferencePrompt(BaseInferencePrompt):
    """Enhanced prompt for inferring both parameter types and string subtypes using LLMs."""

    def __init__(
        self, callable_obj: Callable[..., Any], subtypes: OrderedSet[str] | None = None
    ) -> None:
        """Creates a new TypeAndSubtypeInferencePrompt.

        Args:
            callable_obj: the callable object for which types should be inferred
            subtypes: list of known string subtypes (e.g., "email", "url", etc.)
        """
        super().__init__(callable_obj, subtypes)

    def build_user_prompt(self) -> str:
        """Build the complete prompt for type and subtype inference."""
        template = textwrap.dedent(
            """
            You are tasked with inferring parameter types and string subtypes for a given Python
            function.

            ## Module Context
            - Imports in the module:
            {imports}

            - Parent class name:
            {parent_class}

            - All classes in the same module:
            {all_classes}

            - Known string subtypes:
            {subtype_list}

            ## Available Faker Generators
            When a parameter is a string, you must recommend using a Faker generator for
            more realistic test data.

            Available Faker generators:
            {faker_generators}

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
            For string parameters, also recommend either:
            1. A Faker generator name from the available list (e.g., "email", "ipv4", "url")
            2. A custom regex pattern if no Faker generator matches the expected string format

            Return your answer **only** as JSON in the following format:
            {{
                "param1": {{"type": "<qualname of type>",
                "subtype": "<faker_generator_name or custom_regex>"}},
                "param2": {{"type": "<qualname of type>"}},
                "param3": {{"type": "builtins.str", "subtype": "email"}}
            }}

            For non-string parameters, omit the "subtype" field.
            For string parameters without a specific subtype, omit the "subtype" field.
            For string parameters with a Faker generator or regex, include the "subtype" field.
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
            faker_generators=self._get_faker_generators(),
        )
        return f"{formatted_template}"

    @staticmethod
    def _get_faker_generators() -> str:
        """Get a formatted list of available Faker generators."""
        from pynguin.analyses.string_subtype_inference import (  # noqa: PLC0415
            AVAILABLE_GENERATORS,
        )

        generators = AVAILABLE_GENERATORS
        return ", ".join(generators) if generators else "(none)"


def get_type_and_subtype_inference_system_prompt() -> str:
    """Build the system prompt for type and subtype inference."""
    return textwrap.dedent(
        """
            You are a Python type and string subtype inference engine.
            Your task is to analyze given Python functions and infer both parameter types
            and appropriate string subtypes (using Faker generators or regex patterns).

            Think step by step. Before inferring types, analyze the given context.
            Reason about each parameter's type based on usage and context.
            Keep this reasoning to yourself and do not include it in the final output.

            Use your knowledge of programming, common libraries, and best practices to infer types.
            Use the provided context to make an informed decision about the types of parameters.

            Always return results in full qualified names, e.g., typing.List[builtins.int].
            *NEVER* use Any or object as a type.
            Only infer types for parameters, exclude self and return types.
            Return your output in JSON format only.

            For string parameters:
            1. Check if a Faker generator from the available list matches the expected format.
            2. If a Faker generator matches, use its name in the "subtype" field.
            3. If no Faker generator matches, provide a custom regex pattern instead.
            4. If the string has no specific format requirements, omit the "subtype" field.

            Prefer Faker generators over custom regex patterns when possible, as they provide
            more diverse and realistic test data.
            """
    ).strip()
