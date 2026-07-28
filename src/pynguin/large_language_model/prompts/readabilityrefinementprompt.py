#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2024 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT

"""Provides prompt class for refining test readability."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pynguin.large_language_model.prompts.prompt import Prompt

if TYPE_CHECKING:
    from pynguin.large_language_model.request import RenderedRequest


class ReadabilityRefinementPrompt(Prompt):
    """Implementation prompt for improving readability of a test case."""

    _resource_name = "readability_refinement"

    def __init__(self, sut_context: str, focal_method: str, test_code: str):
        """Creates a new prompt.

        Args:
            sut_context: Formatted context documentation of SUT.
            focal_method: Name of the focal method.
            test_code: The test case code to refine.
        """
        self.sut_context = sut_context
        self.focal_method = focal_method
        self.test_code = test_code
        super().__init__()

    def _template_vars(self) -> list[str]:
        return ["sut_context", "focal_method", "test_code"]

    def render_request(self) -> RenderedRequest:
        """Builds the rendered request.

        Returns:
            The rendered request.
        """
        return self.render(
            sut_context=self.sut_context,
            focal_method=self.focal_method,
            test_code=self.test_code,
        )
