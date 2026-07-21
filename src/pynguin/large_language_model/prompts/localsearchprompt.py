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
from pynguin.large_language_model.request import RenderedRequest
from pynguin.utils.report import LineAnnotation


class LocalSearchPrompt(Prompt):
    """Implementation prompt for local search with LLMs."""

    _logger = logging.getLogger(__name__)
    _resource_name = "local_search"

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
        self.test_case_code = add_line_numbers(test_case_code)
        self.position = position
        self.module_code = module_code
        self.branch_coverage = branch_coverage
        super().__init__()

    def _template_vars(self) -> list[str]:
        return ["position", "branch_coverage", "test_case_code", "module_code"]

    def render_request(self) -> RenderedRequest:
        """Builds the rendered request.

        Returns:
            The rendered request.
        """
        self._logger.debug("Initial test case:\n%s", self.test_case_code)
        uncovered_branches_list = self.build_uncovered_branch_section()
        return self.render(
            position=self.position + 2,
            branch_coverage=uncovered_branches_list,
            test_case_code=self.test_case_code,
            module_code=self.module_code,
        )

    def build_uncovered_branch_section(self) -> list[str]:
        """Builds the uncovered branch section."""
        return [
            f"Line {line.line_no}: Covered {line.branches.covered} of {line.branches.existing}"
            for line in self.branch_coverage
            if line.branches.covered > 0
        ]
