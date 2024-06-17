#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2024 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
from LLM.prompts.prompt import Prompt


class TestCaseGenerationPrompt(Prompt):
    def build_prompt(self) -> str:
        return f"""Write comprehensive unit tests for each method in the module located at the path `{self.module_path}`
            Details:
            - Include one test case per method.
            - The goal of these test cases should mainly be focused on the coverage, no assertions needed.
            - import any external dependency.
            - Ensure each test verifies expected behaviors, edge cases, and error handling.
            - Use meaningful test case names that clearly describe the test's purpose.
            - The module code to be tested: `{self.module_code}\n`.
            Can you provide this test file?
            """
