#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides enhanced prompt for type and subtype inference using LLMs."""

from collections.abc import Callable
from typing import Any

from pynguin.large_language_model.prompts.base_inference_prompt import BaseInferencePrompt
from pynguin.large_language_model.request import RenderedRequest
from pynguin.utils.orderedset import OrderedSet

_ROLE_USER = "<|user|>"


class TypeAndSubtypeInferencePrompt(BaseInferencePrompt):
    """Enhanced prompt for inferring both parameter types and string subtypes using LLMs."""

    _resource_name = "type_subtype_inference"

    def __init__(
        self, callable_obj: Callable[..., Any], subtypes: OrderedSet[str] | None = None
    ) -> None:
        """Creates a new TypeAndSubtypeInferencePrompt.

        Args:
            callable_obj: the callable object for which types should be inferred
            subtypes: list of known string subtypes (e.g., "email", "url", etc.)
        """
        super().__init__(callable_obj, subtypes)

    def _template_vars(self) -> list[str]:
        return [
            "imports",
            "parent_class",
            "all_classes",
            "subtype_list",
            "faker_generators",
            "signature",
            "docstring",
            "body",
            "other_functions",
        ]

    def render_request(self) -> RenderedRequest:
        """Renders the RenderedRequest for type and subtype inference."""
        return self.render(
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

    def build_user_prompt(self) -> str:
        """Build the complete prompt for type and subtype inference."""
        return self.render_request().messages[-1]["content"]

    @staticmethod
    def _get_faker_generators() -> str:
        """Get a formatted list of available Faker generators."""
        from pynguin.analyses.string_subtype_inference import (  # noqa: PLC0415
            AVAILABLE_GENERATORS,
        )

        generators = AVAILABLE_GENERATORS
        return ", ".join(generators) if generators else "(none)"
