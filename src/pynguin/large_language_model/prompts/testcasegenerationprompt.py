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

    def build_prompt(self) -> str:
        """Builds prompt message."""
        test_case_example = """
        def test_method_x():
            str0 = 'x'
            str1 = 'z'
            class_var = Example()
            class_var.method_x(user0, str2)
        """

        return (
            "Write comprehensive unit tests to cover methods in the module located at "
            f"the path `{self.module_code}`\n"
            "Guidelines:\n"
            "- Create one test case for each method in the module.\n"
            "- Cover standard inputs, edge cases, and error handling.\n"
            "- Please no assertions in these tests, focus mainly on the coverage.\n\n"
            f"Example Test Case:\n{test_case_example}\n"
            f"Module code:\n{self.module_code}"
        )
