#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2024 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides class prompt for generating assertions for a test case."""

from pynguin.large_language_model.prompts.prompt import Prompt

class LocalSearchPrompt(Prompt):

    def __init__(self, test_case_code: str, test_case_path: str, position: int, module_code: str,
                 module_path: str):
        """Initializes the prompt."""
        super().__init__(module_code, module_path)
        self.test_case_code = test_case_code
        self.test_case_path = test_case_path
        self.position = position


    def build_prompt(self) -> str:
        """Builds the prompt message."""

        return(
            f"Change the input value at position "
            f"{self.position}"
            f" of the test case to achieve higher branch coverage\n"

            f"Test case path: `{self.test_case_path}` \n"
            f"Test case source code: `{self.test_case_code}` \n"
            f"Module path: `{self.module_path}`\n"
            f"Module source code: `{self.module_code}`"
        )

