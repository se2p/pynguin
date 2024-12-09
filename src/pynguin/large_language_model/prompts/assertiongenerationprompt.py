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
            test_case_source_code: The test case to generate assertion for.
            module_source_code: The source code of the module under test.
        """
        self._test_case_source_code = test_case_source_code
        self._module_source_code = module_source_code

    def build_prompt(self) -> str:
        """Builds prompt message."""
        return f"""Hi GPT! Please generate assertions for
        the following test case (return python code only):
        `{self._test_case_source_code}`
        ### Add assertions below ###
        Source code: `{self._module_source_code}`
        """
