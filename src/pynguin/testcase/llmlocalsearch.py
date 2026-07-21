#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
"""Provides the hook for LLM-based local search.

The LLM local-search round trip is not yet implemented for the libcst test-case
representation, so :meth:`LLMLocalSearch.llm_local_search` is a no-op that always
reports "no improvement". :class:`LLMLocalSearch` is nonetheless kept importable
so that :mod:`pynguin.testcase.localsearch` can wire it up once the round trip
lands. ``local_search_llm`` stays default-off (see ``configuration.py``), so
classic local search does not depend on this being finished.

Re-enabling it means serializing the test case, shortening the LLM context to the
statement's forward dependencies, and deserializing the reply with
:class:`pynguin.large_language_model.parsing.deserializer.CstStatementDeserializer`.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pynguin.ga.testcasechromosome import TestCaseChromosome
    from pynguin.ga.testsuitechromosome import TestSuiteChromosome
    from pynguin.testcase.execution import TestCaseExecutor
    from pynguin.testcase.localsearchobjective import LocalSearchObjective
    from pynguin.testcase.testfactory import TestFactory


class LLMLocalSearch:
    """Hook for LLM-based local search; not yet re-implemented (see module docstring)."""

    _logger = logging.getLogger(__name__)

    def __init__(
        self,
        chromosome: TestCaseChromosome,
        objective: LocalSearchObjective,
        factory: TestFactory,
        suite: TestSuiteChromosome,
        executor: TestCaseExecutor,
    ) -> None:
        """Initializes the (inert) LLM local search hook.

        Args:
            chromosome: The test case chromosome to search.
            objective: The objective to check if improvements are made.
            factory: The factory to modify the test case.
            suite: The test suite containing the test case.
            executor: The executor to run the test cases.
        """
        self._chromosome = chromosome
        self._objective = objective
        self._factory = factory
        self._suite = suite
        self._executor = executor

    def llm_local_search(self, position: int) -> bool:
        """No-op placeholder for LLM-based local search on a single statement.

        Args:
            position: The index of the statement to search.

        Returns:
            Always ``False`` -- see module docstring for re-enablement steps.
        """
        self._logger.debug(
            "LLM local search is not yet re-implemented for the libcst "
            "representation (position %d); skipping.",
            position,
        )
        return False
