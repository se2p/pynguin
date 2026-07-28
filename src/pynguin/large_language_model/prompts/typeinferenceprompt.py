#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2024 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides class prompt for type inference using LLMs."""

from collections.abc import Callable
from typing import Any

from pynguin.large_language_model.prompts.base_inference_prompt import BaseInferencePrompt
from pynguin.large_language_model.request import RenderedRequest
from pynguin.utils.orderedset import OrderedSet

_ROLE_USER = "<|user|>"


class TypeInferencePrompt(BaseInferencePrompt):
    """Implementation prompt for type inference using LLMs."""

    _resource_name = "type_inference"

    def __init__(
        self, callable_obj: Callable[..., Any], subtypes: OrderedSet[str] | None = None
    ) -> None:
        """Creates a new TypeInferencePrompt.

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
            "signature",
            "docstring",
            "body",
            "other_functions",
        ]

    def render_request(self) -> RenderedRequest:
        """Renders the RenderedRequest for type inference."""
        return self.render(
            parent_class=self._get_parent_class_name(self.callable_obj),
            imports=self._get_imports(self.callable_obj),
            all_classes=self._get_all_classes_in_module(),
            other_functions=self._get_all_function_signatures_in_class(self.callable_obj),
            signature=self._get_signature_str(self.callable_obj),
            docstring=self._get_docstring(self.callable_obj),
            body=self._get_src_code(self.callable_obj),
            subtype_list=self._get_str_subtypes(),
        )

    def build_user_prompt(self) -> str:
        """Build the complete prompt for type inference."""
        return self.render_request().messages[-1]["content"]
