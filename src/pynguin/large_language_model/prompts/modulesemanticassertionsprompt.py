#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT

"""Provides prompt class for generating semantic assertions across a whole module."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pynguin.large_language_model.prompts.prompt import Prompt

if TYPE_CHECKING:
    from pynguin.large_language_model.request import RenderedRequest


class ModuleSemanticAssertionsPrompt(Prompt):
    """Prompt for adding semantic assertions to every test in a module at once."""

    _resource_name = "module_semantic_assertions"

    def __init__(self, module_test_code: str, sut_context: str):
        """Creates a new prompt.

        Args:
            module_test_code: The whole test module (imports + all test functions).
            sut_context: Formatted context documentation of the SUT.
        """
        self.module_test_code = module_test_code
        self.sut_context = sut_context
        super().__init__()

    def _template_vars(self) -> list[str]:
        return ["module_test_code", "sut_context"]

    def render_request(self) -> RenderedRequest:
        """Builds the rendered request.

        Returns:
            The rendered request.
        """
        return self.render(
            module_test_code=self.module_test_code,
            sut_context=self.sut_context,
        )
