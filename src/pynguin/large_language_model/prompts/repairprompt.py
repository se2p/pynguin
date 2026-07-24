#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2024 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT

"""Provides prompt class for repairing broken test cases."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pynguin.large_language_model.prompts.prompt import Prompt

if TYPE_CHECKING:
    from pynguin.large_language_model.request import RenderedRequest


class RepairPrompt(Prompt):
    """Implementation prompt for repairing a broken test case."""

    _resource_name = "repair"

    def __init__(
        self,
        broken_code: str,
        error_message: str,
        dependencies: str = "",
        usage_examples: str = "",
    ):
        """Creates a new prompt.

        Args:
            broken_code: The broken test code.
            error_message: The error message/traceback.
            dependencies: Optional SUT dependency signatures.
            usage_examples: Optional call-site usage examples.
        """
        self.broken_code = broken_code
        self.error_message = error_message
        self.dependencies = dependencies
        self.usage_examples = usage_examples
        super().__init__()

    def _template_vars(self) -> list[str]:
        return ["broken_code", "error_message", "dependencies", "usage_examples"]

    def render_request(self) -> RenderedRequest:
        """Builds the rendered request.

        Returns:
            The rendered request.
        """
        return self.render(
            broken_code=self.broken_code,
            error_message=self.error_message,
            dependencies=self.dependencies,
            usage_examples=self.usage_examples,
        )
