#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides island migration as an extension of DynaMOSA's generation loop.

The orchestrator attaches it to each island's DynaMOSAAlgorithm when migration
is enabled; it is not a search algorithm of its own.
"""

from __future__ import annotations

import dataclasses
import logging
from typing import TYPE_CHECKING, cast

import pynguin.configuration as config
from pynguin.ga.operators.selection import RankSelection
from pynguin.islands.migration import MigrationMessage, compute_test_case_hash
from pynguin.utils import randomness

if TYPE_CHECKING:
    import pynguin.ga.computations as ff
    import pynguin.ga.coveragegoals as bg
    import pynguin.ga.testcasechromosome as tcc
    import pynguin.testcase.testcase as tc
    from pynguin.ga.algorithms.dynamosaalgorithm import DynaMOSASearchView
    from pynguin.islands.migration import MigrationChannel


# Selection pressure used for Whitley's linear rank selection. The value is set to
# the upper bound of the range defined by the selection method.
_WHITLEY_SELECTION_PRESSURE = 2.0


@dataclasses.dataclass
class MigrationStats:
    """One island's migration event counts for this run, for cross-process
    statistics logging.
    """  # noqa: D205

    goal_triggered_sent: int = 0
    periodic_sent: int = 0
    received: int = 0
    dedup_drops: int = 0


def ring_destination(island_id: int, num_islands: int) -> int:
    """Computes the single ring neighbor an island sends periodic migrants to.

    Args:
        island_id: This island's own id.
        num_islands: The total number of islands N.

    Returns:
        The next island id in the ring, wrapping from N-1 back to 0.
    """
    return (island_id + 1) % num_islands


def _select_migrants_random(
    population: list[tcc.TestCaseChromosome], k: int
) -> list[tcc.TestCaseChromosome]:
    """Selects k individuals uniformly at random, with replacement."""
    if not population:
        return []
    return randomness.choices(population, k=k)


def _select_migrants_best(
    population: list[tcc.TestCaseChromosome], k: int
) -> list[tcc.TestCaseChromosome]:
    """Select up to ``k`` individuals using the population ranking.

    Individuals are ordered by rank first and crowding distance second, matching
    the ordering used during survivor selection.

    Args:
        population: Population to select from.
        k: Maximum number of individuals to select.

    Returns:
        The selected individuals, without replacement.
    """
    if not population:
        return []
    ranked = sorted(population, key=lambda c: (c.rank, -c.distance))
    return ranked[:k]


def _select_migrants_rank(
    population: list[tcc.TestCaseChromosome], k: int
) -> list[tcc.TestCaseChromosome]:
    """Select ``k`` individuals using Whitley's linear rank selection.

    The population is ordered by rank and crowding distance before sampling.
    Selection is performed with replacement by Pynguin's RankSelection, using
    the migration selection pressure instead of the search's rank bias.

    Args:
        population: Population to select from.
        k: Number of individuals to select.

    Returns:
        The selected individuals.
    """
    if not population:
        return []
    ranked = sorted(population, key=lambda c: (c.rank, -c.distance))
    selection: RankSelection[tcc.TestCaseChromosome] = RankSelection(
        bias=_WHITLEY_SELECTION_PRESSURE
    )
    return selection.select(ranked, k)


_SELECTION_FUNCTIONS = {
    config.MigrantSelectionPolicy.RANDOM: _select_migrants_random,
    config.MigrantSelectionPolicy.BEST: _select_migrants_best,
    config.MigrantSelectionPolicy.RANK: _select_migrants_rank,
}


def select_migrants(
    population: list[tcc.TestCaseChromosome],
    k: int,
    policy: config.MigrantSelectionPolicy,
) -> list[tcc.TestCaseChromosome]:
    """Selects k periodic migrants from population per the configured policy.

    Args:
        population: The sending island's own local population to select from.
        k: The number of individuals to select.
        policy: Which selection policy to use.

    Returns:
        The selected individuals; fewer than k only if population itself has
        fewer than k individuals (RANDOM/RANK still draw with replacement, so
        this only affects BEST or an empty population).
    """
    return _SELECTION_FUNCTIONS[policy](population, k)


class IslandMigrationExtension:
    """Goal-triggered and periodic migration for one island's DynaMOSA search.

    The active migration mechanisms are selected through
    `config.island.migration_strategy`. In `COMBINED` mode, goal-triggered
    and periodic migration run independently and share the same deduplication state.
    """

    _logger = logging.getLogger(__name__)

    def __init__(
        self, island_id: int, channel: MigrationChannel, search: DynaMOSASearchView
    ) -> None:
        """Connects migration to an island's search.

        Create it after the search algorithm is fully configured, because it
        registers a callback on the search's archive.

        Args:
            island_id: This island's id, included in outgoing messages.
            channel: The island's migration channel.
            search: The island's search, for its archive callback.
        """
        self._island_id = island_id
        self._migration_channel = channel
        self._migration_strategy = config.configuration.island.migration_strategy
        self._seen_migration_hashes: set[str] = set()
        self._pending_broadcasts: list[ff.TestCaseFitnessFunction] = []
        self._local_generation = 0
        self.stats = MigrationStats()
        if self._migration_strategy in {
            config.MigrationStrategy.GOAL_TRIGGERED,
            config.MigrationStrategy.COMBINED,
        }:
            search.register_on_target_covered(self._pending_broadcasts.append)

    def after_local_search(self, search: DynaMOSASearchView) -> None:
        """Sends and receives migrants per the configured migration strategy.

        Incoming migrants go through search.integrate_external_test_cases(), so
        they join the population and update the goals manager like any other
        individual, and are never written to the archive directly.

        Args:
            search: The island's search.
        """
        self._maybe_broadcast_goal_triggered(search)
        self._maybe_send_periodic_migrants(search)
        self._drain_incoming_migrants(search)

    def _maybe_broadcast_goal_triggered(self, search: DynaMOSASearchView) -> None:
        """Broadcasts a test case for each target newly covered since last call."""
        for target in self._pending_broadcasts:
            solution = search.covering_solution(target)
            if solution is None:
                continue
            clone = solution.test_case.clone()
            content_hash = compute_test_case_hash(clone)
            if content_hash in self._seen_migration_hashes:
                self.stats.dedup_drops += 1
                continue
            self._seen_migration_hashes.add(content_hash)
            branch_fitness = cast("bg.BranchCoverageTestFitness", target)
            goal = cast("bg.BranchGoal", branch_fitness.goal)
            self._migration_channel.broadcast(
                MigrationMessage(
                    source_island=self._island_id,
                    covered_goal=goal,
                    content_hash=content_hash,
                    test_case=clone,
                )
            )
            self.stats.goal_triggered_sent += 1
            self._logger.info("Island %d broadcast migrant for %s", self._island_id, goal)
        self._pending_broadcasts.clear()

    def _maybe_send_periodic_migrants(self, search: DynaMOSASearchView) -> None:
        """Every F local generations, sends K migrants to the ring neighbor only.

        The migration frequency, number of migrants, and selection policy are read from
        config.island on each call to allow tuning these parameters without rebinding
        the migration strategy.
        """
        self._local_generation += 1
        if self._migration_strategy not in {
            config.MigrationStrategy.PERIODIC,
            config.MigrationStrategy.COMBINED,
        }:
            return
        island_config = config.configuration.island
        frequency = island_config.periodic_migration_frequency
        if frequency <= 0 or self._local_generation % frequency != 0:
            return
        destination = ring_destination(self._island_id, island_config.num_islands)
        migrants = select_migrants(
            search.population_snapshot(),
            island_config.periodic_migration_size,
            island_config.migrant_selection_policy,
        )
        sent = 0
        for chromosome in migrants:
            clone = chromosome.test_case.clone()
            content_hash = compute_test_case_hash(clone)
            if content_hash in self._seen_migration_hashes:
                self.stats.dedup_drops += 1
                continue
            self._seen_migration_hashes.add(content_hash)
            self._migration_channel.send_to(
                destination,
                MigrationMessage(
                    source_island=self._island_id,
                    covered_goal=None,
                    content_hash=content_hash,
                    test_case=clone,
                ),
            )
            sent += 1
        self.stats.periodic_sent += sent
        self._logger.info(
            "Island %d sent %d periodic migrant(s) to island %d",
            self._island_id,
            sent,
            destination,
        )

    def _drain_incoming_migrants(self, search: DynaMOSASearchView) -> int:
        """Add unseen migrants from this island's inbox to the search.

        Shared by goal-triggered, periodic, and LLM Global Broadcast migrants --
        they all arrive through the same channel and the same dedup set.

        Returns:
            The number of new migrants added to the search's population.
        """
        accepted: list[tc.TestCase] = []
        for message in self._migration_channel.drain_incoming():
            if message.content_hash in self._seen_migration_hashes:
                self.stats.dedup_drops += 1
                continue
            self._seen_migration_hashes.add(message.content_hash)
            self._logger.info(
                "Island %d received migrant from island %d for %s",
                self._island_id,
                message.source_island,
                message.covered_goal,
            )
            accepted.append(message.test_case)
        self.stats.received += len(accepted)
        return search.integrate_external_test_cases(accepted)
