#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2024 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides class prompt for generating assertions for a test case."""

from pynguin.large_language_model.prompts.prompt import Prompt
from pynguin.utils.report import LineAnnotation


class LocalSearchPrompt(Prompt):
    """A prompt for local search."""

    def __init__(
        self,
        test_case_code: str,
        position: int,
        module_code: str,
        branch_coverage: list[LineAnnotation],
    ):
        """Initializes the prompt."""
        super().__init__(module_code, "")
        self.test_case_code = test_case_code
        self.position = position
        self.branch_coverage = branch_coverage

    def build_prompt(self) -> str:
        """Builds the prompt message."""
        uncovered_branches_list = self.build_uncovered_branch_section()
        uncovered_branches = "\n".join(uncovered_branches_list)

        return (
            f"Change the input value at position "
            f"{self.position}"
            f" of the test case to achieve higher branch coverage\n"
            f"Make sure that the call really changes the branch coverage and add the needed call "
            f"if necessary.\n"
            f"Give back only the whole test and not the variable itself as Python code for better "
            f"parsing\n"
            f"Also add a class where the test is in to the test_code.\n"
            f"Line of branches we failed to cover:\n"
            f"{uncovered_branches}\n"
            f"Test case source code:\n `{self.test_case_code}` \n"
            f"Module source code:\n `{self.module_code}`"
        )

    def build_uncovered_branch_section(self) -> list[str]:
        """Builds the uncovered branch section."""
        return [
            f"Line {line.line_no}: Covered {line.branches.covered} of {line.branches.existing}"
            for line in self.branch_coverage
            if line.branches.covered > 0
        ]
