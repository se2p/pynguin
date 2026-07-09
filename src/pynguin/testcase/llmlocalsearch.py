#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
"""Provides the (currently inert) hook for LLM-based local search.

The LLM local-search round trip has not been re-implemented for the libcst
test-case representation. ``REENABLEMENT_PLAN.md`` (section "1. Local search",
design point (f)) lays out how to do it:

1. Serialize the test case via ``test_case.to_test_function().code`` instead of the
   removed ``unparse_test_case`` helper.
2. Shorten the LLM context via ``test_case.forward_dependencies(position)`` plus
   ``statement.accessible`` instead of the removed
   ``get_forward_dependencies``/``accessible_object()`` APIs.
3. Deserialize the LLM's reply with a small dedicated CST-based parser (proposed at
   ``src/pynguin/large_language_model/parsing/cst_deserializer.py``) instead of
   resurrecting the old, now-shimmed ``deserializer.py``.

Step 3 lives in the ``large_language_model`` package, which is out of scope for this
change (it is being re-enabled concurrently as its own subsystem). Until it lands,
this module only keeps :class:`LLMLocalSearch` importable so that
:mod:`pynguin.testcase.localsearch` can wire it up; :meth:`LLMLocalSearch.llm_local_search`
is a no-op that always reports "no improvement". ``local_search_llm`` stays
default-off (see ``configuration.py``), so classic local search does not depend on
this being finished.
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
