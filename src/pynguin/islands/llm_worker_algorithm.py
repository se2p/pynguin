#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides centralized-LLM-worker integration as an extension of DynaMOSA's loop.

The orchestrator attaches it to each island's DynaMOSAAlgorithm when the LLM
worker is enabled. The island itself never queries the LLM: it reports coverage
to the worker and ingests the test cases the worker sends back.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, cast

from pynguin.islands.llm_worker_protocol import StatusReport
from pynguin.utils.orderedset import OrderedSet

if TYPE_CHECKING:
    import pynguin.ga.computations as ff
    import pynguin.ga.coveragegoals as bg
    from pynguin.ga.algorithms.dynamosaalgorithm import DynaMOSASearchView
    from pynguin.islands.llm_worker_protocol import LLMWorkerChannel

_LOGGER = logging.getLogger(__name__)


class IslandLLMWorkerExtension:
    """Reports an island's callable coverage to the LLM worker and add results."""

    def __init__(
        self, island_id: int, channel: LLMWorkerChannel, search: DynaMOSASearchView
    ) -> None:
        """Connects an island's search to its LLM worker channel.

        Create it after the search algorithm is fully configured, because it
        registers an archive callback and maps goals to code objects.

        Args:
            island_id: This island's own id, included in outgoing status reports.
            channel: This island's view of the LLM worker channel.
            search: The island's search.
        """
        self._island_id = island_id
        self._llm_worker_channel = channel
        self._last_seen_active_goals: OrderedSet = OrderedSet()
        self._pending_llm_covered: list[ff.TestCaseFitnessFunction] = []
        search.register_on_target_covered(self._pending_llm_covered.append)
        self._goals_by_code_object_id: dict[int, list] = {}
        for fitness in search.test_case_fitness_functions:
            branch_fitness = cast("bg.BranchCoverageTestFitness", fitness)
            self._goals_by_code_object_id.setdefault(branch_fitness.goal.code_object_id, []).append(
                branch_fitness
            )

    def after_local_search(self, search: DynaMOSASearchView) -> None:
        """Reports updated coverage, then ingests completed LLM results.

        Only callables affected in the current generation are reported. Received
        test cases go through search.integrate_external_test_cases(), so they
        join the population and update the goals manager like any other
        individual, and are never written to the archive directly.

        Args:
            search: The island's search.
        """
        current_goals = search.current_goals_snapshot()
        newly_unlocked = current_goals - self._last_seen_active_goals
        self._last_seen_active_goals = current_goals

        touched_code_object_ids: set[int] = set()
        for goal in newly_unlocked:
            branch_fitness = cast("bg.BranchCoverageTestFitness", goal)
            touched_code_object_ids.add(branch_fitness.goal.code_object_id)
        for target in self._pending_llm_covered:
            branch_fitness = cast("bg.BranchCoverageTestFitness", target)
            touched_code_object_ids.add(branch_fitness.goal.code_object_id)
        self._pending_llm_covered.clear()

        subject_properties = search.subject_properties
        covered_goals = search.covered_goals_snapshot()
        for code_object_id in touched_code_object_ids:
            goals = self._goals_by_code_object_id.get(code_object_id)
            if not goals:
                continue
            code_object_meta = subject_properties.existing_code_objects.get(code_object_id)
            if code_object_meta is None:
                continue
            covered_count = sum(1 for goal in goals if goal in covered_goals)
            coverage = covered_count / len(goals)
            self._llm_worker_channel.report(
                StatusReport(
                    island_id=self._island_id,
                    first_line=code_object_meta.code_object.co_firstlineno,
                    coverage=coverage,
                    covered=coverage >= 1.0,
                )
            )

        ingested = search.integrate_external_test_cases(
            result.test_case for result in self._llm_worker_channel.drain_incoming()
        )
        if ingested:
            _LOGGER.info(
                "Island %d ingested %d test case(s) from the LLM worker", self._island_id, ingested
            )
