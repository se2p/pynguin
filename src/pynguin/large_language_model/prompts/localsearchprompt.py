#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2024 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides class prompt for LLM requests for local search."""

import logging

from pynguin.large_language_model.parsing.helpers import add_line_numbers
from pynguin.large_language_model.prompts.prompt import Prompt
from pynguin.utils.report import LineAnnotation


class LocalSearchPrompt(Prompt):
    """Implementation prompt for local search with LLMs."""

    _logger = logging.getLogger(__name__)

    def __init__(
        self,
        test_case_code: str,
        position: int,
        module_code: str,
        branch_coverage: list[LineAnnotation],
    ):
        """Initializes the prompt.

        For better parsing, the code of the module and the testcase should already contain line
        numbers.

        Args:
            test_case_code: The source code of the test case.
            position: The position of the statement to be mutated.
            module_code: The source code of the module under test.
            branch_coverage: The branch coverage information.
        """
        super().__init__(module_code, "")
        self.test_case_code = add_line_numbers(test_case_code)
        self.position = position
        self.branch_coverage = branch_coverage

    def build_prompt(self) -> str:
        """Builds the prompt message."""
        uncovered_branches_list = self.build_uncovered_branch_section()
        uncovered_branches = "\n".join(uncovered_branches_list)
        self._logger.debug("Initial test case:\n%s", self.test_case_code)
        return (
            f"Mutate the statement at position {self.position + 2} of the test case to achieve "
            f"higher branch coverage\n"
            f"Give back only the whole test and not the variable itself as Python code for better "
            f"parsing\n"
            f"Also add a class where the test is in to the test_code.\n"
            f"Pick a branch where mutating the provided statement can actually increase the "
            f"branch coverage.\n"
            f"Line of branches we failed to cover:\n"
            f"{uncovered_branches}\n"
            f"Test case source code:\n `{self.test_case_code}`\n"
            f"Module source code:\n `{self.module_code}`"
        )

    def build_uncovered_branch_section(self) -> list[str]:
        """Builds the uncovered branch section."""
        return [
            f"Line {line.line_no}: Covered {line.branches.covered} of {line.branches.existing}"
            for line in self.branch_coverage
            if line.branches.covered > 0
        ]
