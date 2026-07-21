#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2024 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides class prompt for generating tests for a module."""

from pynguin.large_language_model.prompts.prompt import Prompt
from pynguin.large_language_model.request import RenderedRequest


class TestCaseGenerationPrompt(Prompt):
    """Implementation prompt for generating tests for a module."""

    _resource_name = "test_case_generation"

    def __init__(self, module_code: str, module_path: str):
        """Creates a new prompt.

        Args:
            module_code: The module code to be passed to the prompt.
            module_path: The module file path.
        """
        self.module_code = module_code
        self.module_path = module_path
        super().__init__()

    def _template_vars(self) -> list[str]:
        return ["module_code", "module_path"]

    def render_request(self) -> RenderedRequest:
        """Builds the rendered request.

        Returns:
            The rendered request.
        """
        return self.render(module_code=self.module_code, module_path=self.module_path)
