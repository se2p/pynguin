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
            module_code: the module code to be passed to the prompt.
            module_path: the module file path.
        """
        self.module_code = module_code
        self.module_path = module_path

    def build_prompt(self) -> str:
        """Builds prompt message."""
        return f"""You are a Python developer tasked with writing unit tests
         for a Python module. The module's code is provided below.
         Please generate the corresponding unit tests.
            Requirements:
                - For each function/method, create for each a test case that cover:
                    - Normal expected cases.
                    - Edge cases.
                    - Error cases (e.g., invalid input values).
                - Make sure you import any external dependency.
            Module path: `{self.module_path}`
            Module code: `{self.module_code}`
            """
