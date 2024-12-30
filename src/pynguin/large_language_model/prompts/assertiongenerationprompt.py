#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2024 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides class prompt for generating assertions for a test case."""

from pynguin.large_language_model.prompts.prompt import Prompt


class AssertionGenerationPrompt(Prompt):
    """Implementation prompt for generating assertions for a test case."""

    def __init__(self, test_case_source_code: str, module_source_code: str):
        """Creates a new prompt.

        Args:
            test_case_source_code: The test case to generate assertions for.
            module_source_code: The source code of the module under test.
        """
        super().__init__("", "")
        self._test_case_source_code = test_case_source_code
        self._module_source_code = module_source_code

    def build_prompt(self) -> str:
        """Builds the prompt message."""
        return (
            f"Write assertions for the following test case:\n"
            f"`{self._test_case_source_code}`\n"
            f" ### Add assertions below ###\n\n"
            f"Module source code: `{self._module_source_code}`"
        )
