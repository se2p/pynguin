#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2024 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides class prompt for generating assertions for a test case."""

from pynguin.large_language_model.prompts.prompt import Prompt
from pynguin.large_language_model.request import RenderedRequest


class AssertionGenerationPrompt(Prompt):
    """Implementation prompt for generating assertions for a test case."""

    _resource_name = "assertion_generation"

    def __init__(self, test_case_source_code: str, module_source_code: str):
        """Creates a new prompt.

        Args:
            test_case_source_code: The test case to generate assertions for.
            module_source_code: The source code of the module under test.
        """
        self._test_case_source_code = test_case_source_code
        self._module_source_code = module_source_code
        super().__init__()

    def _template_vars(self) -> list[str]:
        return ["test_case_code", "module_code"]

    def render_request(self) -> RenderedRequest:
        """Builds the rendered request.

        Returns:
            The rendered request.
        """
        return self.render(
            test_case_code=self._test_case_source_code, module_code=self._module_source_code
        )
