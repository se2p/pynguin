#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT

"""Provides prompt class for module-level mutation-driven assertion strengthening."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pynguin.large_language_model.prompts.prompt import Prompt

if TYPE_CHECKING:
    from pynguin.large_language_model.request import RenderedRequest


class ModuleMutationStrengthenPrompt(Prompt):
    """Prompt for strengthening assertions and adding boundary tests across a whole module."""

    _resource_name = "module_mutation_strengthen"

    def __init__(
        self,
        module_code: str,
        module_test_code: str,
        surviving_mutants: str,
    ):
        """Creates a new prompt.

        Args:
            module_code: The source code of the module under test.
            module_test_code: The whole test module (imports + all test functions).
            surviving_mutants: Formatted list of surviving mutants.
        """
        self.module_code = module_code
        self.module_test_code = module_test_code
        self.surviving_mutants = surviving_mutants
        super().__init__()

    def _template_vars(self) -> list[str]:
        return ["module_code", "module_test_code", "surviving_mutants"]

    def render_request(self) -> RenderedRequest:
        """Builds the rendered request.

        Returns:
            The rendered request.
        """
        return self.render(
            module_code=self.module_code,
            module_test_code=self.module_test_code,
            surviving_mutants=self.surviving_mutants,
        )
