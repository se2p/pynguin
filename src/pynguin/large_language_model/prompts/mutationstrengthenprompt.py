#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2024 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT

"""Provides prompt class for mutation-driven assertion strengthening."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pynguin.large_language_model.prompts.prompt import Prompt

if TYPE_CHECKING:
    from pynguin.large_language_model.request import RenderedRequest


class MutationStrengthenPrompt(Prompt):
    """Implementation prompt for strengthening test assertions based on surviving mutants."""

    _resource_name = "mutation_strengthen"

    def __init__(
        self,
        module_code: str,
        test_code: str,
        surviving_mutants: str,
        focal_method: str,
    ):
        """Creates a new prompt.

        Args:
            module_code: The source code of the module under test.
            test_code: The current test code to strengthen.
            surviving_mutants: Description of the surviving mutants.
            focal_method: Name of the focal method.
        """
        self.module_code = module_code
        self.test_code = test_code
        self.surviving_mutants = surviving_mutants
        self.focal_method = focal_method
        super().__init__()

    def _template_vars(self) -> list[str]:
        return ["module_code", "test_code", "surviving_mutants", "focal_method"]

    def render_request(self) -> RenderedRequest:
        """Builds the rendered request.

        Returns:
            The rendered request.
        """
        return self.render(
            module_code=self.module_code,
            test_code=self.test_code,
            surviving_mutants=self.surviving_mutants,
            focal_method=self.focal_method,
        )
