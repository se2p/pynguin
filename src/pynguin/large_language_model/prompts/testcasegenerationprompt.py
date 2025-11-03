#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2024 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides class prompt for generating tests for a module."""

from pynguin.large_language_model.prompts.prompt import Prompt


class TestCaseGenerationPrompt(Prompt):
    """Implementation prompt for generating tests for a module."""

    def __init__(self, module_code: str, module_path: str):
        """Creates a new prompt.

        Args:
            module_code: The module code to be passed to the prompt.
            module_path: The module file path.
        """
        super().__init__(module_code, module_path)
        self.module_code = module_code
        self.module_path = module_path

    def build_prompt(self) -> str:
        """Builds the prompt message."""
        return (
            f"Write unit tests for the following module. Don't use unittest, "
            f"but only pytest.\n"
            f"Module path: `{self.module_path}`\n"
            f"Module source code: `{self.module_code}`"
        )
