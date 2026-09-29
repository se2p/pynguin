#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Tests for the island-migration-aware DynaMOSA variant."""

import dataclasses
from unittest.mock import MagicMock

import pytest

import pynguin.configuration as config
import pynguin.ga.testcasechromosome as tcc
from pynguin.ga.algorithms.dynamosaalgorithm import DynaMOSAAlgorithm
from pynguin.islands import migration_algorithm
from pynguin.islands.migration import MigrationMessage, compute_test_case_hash


@dataclasses.dataclass
class _FakeTestCase:
    """A plain stand-in for TestCase -- only to_code()/clone() are exercised here."""

    source: str

    def to_code(self) -> str:
        return self.source

    def clone(self) -> "_FakeTestCase":
        return _FakeTestCase(self.source)


@pytest.fixture
def island_algorithm(monkeypatch):
    """A plain DynaMOSAAlgorithm with mocked components, mirroring
    tests/ga/algorithms/test_lldynamosaalgorithm.py's lldynamosa_algorithm fixture.
    """  # noqa: D205
    monkeypatch.setattr(
        config.configuration.island, "migration_strategy", config.MigrationStrategy.GOAL_TRIGGERED
    )
    algorithm = DynaMOSAAlgorithm()
    algorithm._logger = MagicMock()
    algorithm._archive = MagicMock()
    algorithm._goals_manager = MagicMock()
    algorithm._population = []
    algorithm.test_factory = MagicMock()
    algorithm.test_case_fitness_functions = []  # type: ignore[assignment]
    return algorithm


def _bind(algorithm, channel, island_id=0):
    extension = migration_algorithm.IslandMigrationExtension(island_id, channel, algorithm)
    algorithm.add_generation_extension(extension)
    return extension


def test_bind_migration_registers_callback_on_archive(island_algorithm):
    channel = MagicMock()

    extension = _bind(island_algorithm, channel, 0)

    island_algorithm._archive.add_on_target_covered.assert_called_once_with(
        extension._pending_broadcasts.append
    )
    assert extension._island_id == 0
    assert extension._migration_channel is channel
    assert extension._seen_migration_hashes == set()


def test_maybe_migrate_broadcasts_newly_covered_target(island_algorithm):
    channel = MagicMock()
    channel.drain_incoming.return_value = []
    extension = _bind(island_algorithm, channel, 0)
    target = MagicMock()
    target.goal = "some-goal"
    covering_chromosome = MagicMock()
    covering_chromosome.test_case = _FakeTestCase("def test_0():\n    pass\n")
    island_algorithm._archive.get_covering_solution.return_value = covering_chromosome
    extension._pending_broadcasts.append(target)

    extension.after_local_search(island_algorithm)

    channel.broadcast.assert_called_once()
    (message,) = channel.broadcast.call_args.args
    assert isinstance(message, MigrationMessage)
    assert message.source_island == 0
    assert message.covered_goal == "some-goal"
    assert message.content_hash == compute_test_case_hash(covering_chromosome.test_case)
    assert extension._pending_broadcasts == []


def test_maybe_migrate_skips_target_with_no_covering_solution(island_algorithm):
    channel = MagicMock()
    channel.drain_incoming.return_value = []
    extension = _bind(island_algorithm, channel, 0)
    island_algorithm._archive.get_covering_solution.return_value = None
    extension._pending_broadcasts.append(MagicMock())

    extension.after_local_search(island_algorithm)

    channel.broadcast.assert_not_called()


def test_maybe_migrate_skips_already_broadcast_hash(island_algorithm):
    channel = MagicMock()
    channel.drain_incoming.return_value = []
    extension = _bind(island_algorithm, channel, 0)
    target = MagicMock()
    covering_chromosome = MagicMock()
    covering_chromosome.test_case = _FakeTestCase("def test_0():\n    pass\n")
    island_algorithm._archive.get_covering_solution.return_value = covering_chromosome
    extension._seen_migration_hashes.add(compute_test_case_hash(covering_chromosome.test_case))
    extension._pending_broadcasts.append(target)

    extension.after_local_search(island_algorithm)

    channel.broadcast.assert_not_called()


def test_maybe_migrate_drains_incoming_and_updates_goals_manager(island_algorithm):
    channel = MagicMock()
    extension = _bind(island_algorithm, channel, 0)
    incoming_test_case = _FakeTestCase("def test_0():\n    pass\n")
    message = MigrationMessage(
        source_island=1,
        covered_goal="peer-goal",  # type: ignore[arg-type]
        content_hash=compute_test_case_hash(incoming_test_case),  # type: ignore[arg-type]
        test_case=incoming_test_case,  # type: ignore[arg-type]
    )
    channel.drain_incoming.return_value = [message]

    extension.after_local_search(island_algorithm)

    assert len(island_algorithm._population) == 1
    assert island_algorithm._population[0].test_case is incoming_test_case
    island_algorithm._goals_manager.update.assert_called_once_with(island_algorithm._population)


def test_maybe_migrate_skips_duplicate_incoming_messages(island_algorithm):
    channel = MagicMock()
    extension = _bind(island_algorithm, channel, 0)
    incoming_test_case = _FakeTestCase("def test_0():\n    pass\n")
    content_hash = compute_test_case_hash(incoming_test_case)  # type: ignore[arg-type]
    duplicate_message = MigrationMessage(
        source_island=1,
        covered_goal="peer-goal",  # type: ignore[arg-type]
        content_hash=content_hash,
        test_case=incoming_test_case,  # type: ignore[arg-type]
    )
    channel.drain_incoming.return_value = [duplicate_message, duplicate_message]

    extension.after_local_search(island_algorithm)

    assert len(island_algorithm._population) == 1


def test_maybe_migrate_does_not_update_goals_manager_when_nothing_changed(island_algorithm):
    channel = MagicMock()
    channel.drain_incoming.return_value = []
    extension = _bind(island_algorithm, channel, 0)

    extension.after_local_search(island_algorithm)

    island_algorithm._goals_manager.update.assert_not_called()


def test_maybe_migrate_incoming_chromosome_uses_own_test_factory_and_fitness_functions(
    island_algorithm,
):
    channel = MagicMock()
    extension = _bind(island_algorithm, channel, 0)
    own_fitness_function = MagicMock()
    own_fitness_function.is_maximisation_function.return_value = False
    island_algorithm.test_case_fitness_functions = [own_fitness_function]
    incoming_test_case = _FakeTestCase("def test_0():\n    pass\n")
    message = MigrationMessage(
        source_island=1,
        covered_goal="peer-goal",  # type: ignore[arg-type]
        content_hash=compute_test_case_hash(incoming_test_case),  # type: ignore[arg-type]
        test_case=incoming_test_case,  # type: ignore[arg-type]
    )
    channel.drain_incoming.return_value = [message]

    extension.after_local_search(island_algorithm)

    chromosome = island_algorithm._population[0]
    assert isinstance(chromosome, tcc.TestCaseChromosome)
    assert chromosome.test_factory is island_algorithm.test_factory


@pytest.mark.parametrize(
    ("island_id", "num_islands", "expected"),
    [(0, 4, 1), (1, 4, 2), (2, 4, 3), (3, 4, 0), (0, 1, 0), (5, 6, 0)],
)
def test_ring_destination(island_id, num_islands, expected):
    assert migration_algorithm.ring_destination(island_id, num_islands) == expected


def _fake_chromosome(source: str, rank: int, distance: float) -> MagicMock:
    chromosome = MagicMock()
    chromosome.test_case = _FakeTestCase(source)
    chromosome.rank = rank
    chromosome.distance = distance
    return chromosome


@pytest.fixture
def ranked_population() -> list[MagicMock]:
    """Five chromosomes, best-to-worst by (rank, -distance): c0, c1, c2, c3, c4."""
    return [
        _fake_chromosome("def test_0():\n    pass\n", rank=0, distance=5.0),
        _fake_chromosome("def test_1():\n    pass\n", rank=0, distance=1.0),
        _fake_chromosome("def test_2():\n    pass\n", rank=1, distance=3.0),
        _fake_chromosome("def test_3():\n    pass\n", rank=1, distance=2.0),
        _fake_chromosome("def test_4():\n    pass\n", rank=2, distance=0.0),
    ]


def test_select_migrants_random_selects_k_individuals(ranked_population):
    selected = migration_algorithm.select_migrants(
        ranked_population, 3, config.MigrantSelectionPolicy.RANDOM
    )
    assert len(selected) == 3
    assert all(chromosome in ranked_population for chromosome in selected)


def test_select_migrants_random_empty_population():
    assert migration_algorithm.select_migrants([], 3, config.MigrantSelectionPolicy.RANDOM) == []


def test_select_migrants_best_picks_lowest_rank_then_highest_distance(ranked_population):
    selected = migration_algorithm.select_migrants(
        ranked_population, 2, config.MigrantSelectionPolicy.BEST
    )
    assert selected == [ranked_population[0], ranked_population[1]]


def test_select_migrants_best_empty_population():
    assert migration_algorithm.select_migrants([], 2, config.MigrantSelectionPolicy.BEST) == []


def test_select_migrants_rank_selects_k_individuals_from_the_population(ranked_population):
    selected = migration_algorithm.select_migrants(
        ranked_population, 4, config.MigrantSelectionPolicy.RANK
    )
    assert len(selected) == 4
    assert all(chromosome in ranked_population for chromosome in selected)


def test_select_migrants_rank_empty_population():
    assert migration_algorithm.select_migrants([], 3, config.MigrantSelectionPolicy.RANK) == []


def test_select_migrants_rank_r_zero_picks_the_best_individual(monkeypatch, ranked_population):
    monkeypatch.setattr(migration_algorithm.randomness, "next_float", lambda: 0.0)
    selected = migration_algorithm.select_migrants(
        ranked_population, 1, config.MigrantSelectionPolicy.RANK
    )
    assert selected == [ranked_population[0]]


def _set_periodic_config(
    monkeypatch,
    *,
    strategy: config.MigrationStrategy,
    num_islands: int = 4,
    frequency: int = 5,
    size: int = 2,
    policy: config.MigrantSelectionPolicy = config.MigrantSelectionPolicy.RANDOM,
) -> None:
    monkeypatch.setattr(config.configuration.island, "migration_strategy", strategy)
    monkeypatch.setattr(config.configuration.island, "num_islands", num_islands)
    monkeypatch.setattr(config.configuration.island, "periodic_migration_frequency", frequency)
    monkeypatch.setattr(config.configuration.island, "periodic_migration_size", size)
    monkeypatch.setattr(config.configuration.island, "migrant_selection_policy", policy)


def test_periodic_migration_sends_to_ring_neighbor_only_not_broadcast(
    monkeypatch, island_algorithm, ranked_population
):
    """Uses BEST selection so the two migrants are guaranteed distinct (RANDOM
    selects with replacement and could otherwise draw the same individual
    twice, making the exact call count flaky).
    """  # noqa: D205
    _set_periodic_config(
        monkeypatch,
        strategy=config.MigrationStrategy.PERIODIC,
        num_islands=4,
        frequency=1,
        size=2,
        policy=config.MigrantSelectionPolicy.BEST,
    )
    channel = MagicMock()
    channel.drain_incoming.return_value = []
    extension = _bind(island_algorithm, channel, 0)
    island_algorithm._population = ranked_population

    extension.after_local_search(island_algorithm)

    assert channel.send_to.call_count == 2
    destinations = {call.args[0] for call in channel.send_to.call_args_list}
    assert destinations == {1}
    channel.broadcast.assert_not_called()


def _patch_select_migrants_with_fresh_chromosomes(monkeypatch) -> None:
    """Makes each periodic-migration trigger select a distinct, never-before-seen
    chromosome, so frequency-triggering tests are independent of dedup/selection
    policy (both already covered by their own dedicated tests above).
    """  # noqa: D205
    counter = iter(range(1_000_000))

    def _fresh(*_args, **_kwargs):
        index = next(counter)
        return [_fake_chromosome(f"def test_fresh_{index}():\n    pass\n", rank=0, distance=0.0)]

    monkeypatch.setattr(migration_algorithm, "select_migrants", _fresh)


def test_periodic_migration_frequency_one_triggers_every_generation(
    monkeypatch, island_algorithm, ranked_population
):
    _set_periodic_config(
        monkeypatch, strategy=config.MigrationStrategy.PERIODIC, frequency=1, size=1
    )
    _patch_select_migrants_with_fresh_chromosomes(monkeypatch)
    channel = MagicMock()
    channel.drain_incoming.return_value = []
    extension = _bind(island_algorithm, channel, 0)
    island_algorithm._population = ranked_population

    for _ in range(3):
        extension.after_local_search(island_algorithm)

    assert channel.send_to.call_count == 3


def test_periodic_migration_frequency_five_triggers_at_generations_five_and_ten(
    monkeypatch, island_algorithm, ranked_population
):
    _set_periodic_config(
        monkeypatch, strategy=config.MigrationStrategy.PERIODIC, frequency=5, size=1
    )
    _patch_select_migrants_with_fresh_chromosomes(monkeypatch)
    channel = MagicMock()
    channel.drain_incoming.return_value = []
    extension = _bind(island_algorithm, channel, 0)
    island_algorithm._population = ranked_population

    for _ in range(10):
        extension.after_local_search(island_algorithm)

    assert channel.send_to.call_count == 2


def test_periodic_migration_payload_carries_only_the_test_case_not_source_fitness(
    monkeypatch, island_algorithm, ranked_population
):
    _set_periodic_config(
        monkeypatch, strategy=config.MigrationStrategy.PERIODIC, frequency=1, size=1
    )
    channel = MagicMock()
    channel.drain_incoming.return_value = []
    extension = _bind(island_algorithm, channel, 0)
    island_algorithm._population = ranked_population

    extension.after_local_search(island_algorithm)

    (_destination, message), _kwargs = channel.send_to.call_args
    assert isinstance(message, MigrationMessage)
    assert message.covered_goal is None
    assert isinstance(message.test_case, _FakeTestCase)


def test_periodic_migration_dedup_shares_seen_hashes_with_goal_triggered(
    monkeypatch, island_algorithm
):
    _set_periodic_config(
        monkeypatch, strategy=config.MigrationStrategy.COMBINED, frequency=1, size=1
    )
    channel = MagicMock()
    channel.drain_incoming.return_value = []
    extension = _bind(island_algorithm, channel, 0)
    solo = _fake_chromosome("def test_0():\n    pass\n", rank=0, distance=0.0)
    island_algorithm._population = [solo]
    already_sent_hash = compute_test_case_hash(solo.test_case)
    extension._seen_migration_hashes.add(already_sent_hash)

    extension.after_local_search(island_algorithm)

    channel.send_to.assert_not_called()


def test_combined_strategy_fires_both_mechanisms_independently(monkeypatch, island_algorithm):
    _set_periodic_config(
        monkeypatch, strategy=config.MigrationStrategy.COMBINED, frequency=1, size=1
    )
    channel = MagicMock()
    channel.drain_incoming.return_value = []
    extension = _bind(island_algorithm, channel, 0)
    covered_target = MagicMock()
    covered_target.goal = "some-goal"
    covering_chromosome = MagicMock()
    covering_chromosome.test_case = _FakeTestCase("def test_covered():\n    pass\n")
    island_algorithm._archive.get_covering_solution.return_value = covering_chromosome
    extension._pending_broadcasts.append(covered_target)
    island_algorithm._population = [
        _fake_chromosome("def test_periodic():\n    pass\n", rank=0, distance=0.0)
    ]

    extension.after_local_search(island_algorithm)

    channel.broadcast.assert_called_once()
    channel.send_to.assert_called_once()


def test_disabled_strategy_never_sends_periodic_migrants(monkeypatch, island_algorithm):
    _set_periodic_config(monkeypatch, strategy=config.MigrationStrategy.DISABLED, frequency=1)
    channel = MagicMock()
    channel.drain_incoming.return_value = []
    extension = _bind(island_algorithm, channel, 0)
    island_algorithm._population = [
        _fake_chromosome("def test_0():\n    pass\n", rank=0, distance=0.0)
    ]

    extension.after_local_search(island_algorithm)

    channel.send_to.assert_not_called()
    channel.broadcast.assert_not_called()


def test_incoming_migrants_do_not_write_the_archive(island_algorithm):
    channel = MagicMock()
    extension = _bind(island_algorithm, channel)
    island_algorithm._archive.reset_mock()
    incoming_test_case = _FakeTestCase("def test_0():\n    pass\n")
    channel.drain_incoming.return_value = [
        MigrationMessage(
            source_island=1,
            covered_goal="peer-goal",  # type: ignore[arg-type]
            content_hash=compute_test_case_hash(incoming_test_case),  # type: ignore[arg-type]
            test_case=incoming_test_case,  # type: ignore[arg-type]
        )
    ]

    extension.after_local_search(island_algorithm)

    assert island_algorithm._archive.update.call_count == 0
    assert island_algorithm._archive.add_goals.call_count == 0
    assert extension.stats.received == 1
