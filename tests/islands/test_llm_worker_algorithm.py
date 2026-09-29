#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Tests for the island-side LLM-worker generation extension."""

import dataclasses
import logging
from unittest.mock import MagicMock

import pytest

import pynguin.configuration as config
import pynguin.ga.testcasechromosome as tcc
from pynguin.ga.algorithms.dynamosaalgorithm import DynaMOSAAlgorithm
from pynguin.islands import llm_worker_algorithm
from pynguin.islands.llm_worker_protocol import LLMWorkerResult, StatusReport
from pynguin.islands.migration import MigrationMessage, compute_test_case_hash
from pynguin.islands.migration_algorithm import IslandMigrationExtension


@dataclasses.dataclass
class _FakeTestCase:
    """A plain stand-in for TestCase -- only to_code()/clone() are exercised here."""

    source: str

    def to_code(self) -> str:
        return self.source

    def clone(self) -> "_FakeTestCase":
        return _FakeTestCase(self.source)


def _fake_goal(code_object_id: int) -> MagicMock:
    goal = MagicMock()
    goal.code_object_id = code_object_id
    fitness = MagicMock()
    fitness.goal = goal
    return fitness


@pytest.fixture
def island_algorithm():
    """A plain DynaMOSAAlgorithm with mocked components, mirroring
    tests/islands/test_migration_algorithm.py's island_algorithm fixture.
    """  # noqa: D205
    algorithm = DynaMOSAAlgorithm()
    algorithm._logger = MagicMock()
    algorithm._archive = MagicMock()
    algorithm._goals_manager = MagicMock()
    algorithm._population = []
    algorithm.test_factory = MagicMock()
    algorithm.test_case_fitness_functions = []  # type: ignore[assignment]
    algorithm.executor = MagicMock()
    return algorithm


def _bind(algorithm, channel, island_id=0):
    extension = llm_worker_algorithm.IslandLLMWorkerExtension(island_id, channel, algorithm)
    algorithm.add_generation_extension(extension)
    return extension


def test_bind_llm_worker_registers_callback_and_builds_goal_map(island_algorithm):
    channel = MagicMock()
    goal_a = _fake_goal(1)
    goal_b = _fake_goal(1)
    goal_c = _fake_goal(2)
    island_algorithm.test_case_fitness_functions = [goal_a, goal_b, goal_c]

    extension = _bind(island_algorithm, channel, 0)

    island_algorithm._archive.add_on_target_covered.assert_called_once_with(
        extension._pending_llm_covered.append
    )
    assert extension._island_id == 0
    assert extension._llm_worker_channel is channel
    assert extension._goals_by_code_object_id[1] == [goal_a, goal_b]
    assert extension._goals_by_code_object_id[2] == [goal_c]


def test_maybe_report_reports_newly_unlocked_goal(island_algorithm):
    channel = MagicMock()
    channel.drain_incoming.return_value = []
    goal = _fake_goal(1)
    island_algorithm.test_case_fitness_functions = [goal]
    extension = _bind(island_algorithm, channel, 0)
    island_algorithm._goals_manager.current_goals = [goal]
    island_algorithm._archive.covered_goals = []
    code_object_meta = MagicMock()
    code_object_meta.code_object.co_firstlineno = 42
    island_algorithm.executor.subject_properties.existing_code_objects = {1: code_object_meta}

    extension.after_local_search(island_algorithm)

    channel.report.assert_called_once()
    (status,) = channel.report.call_args.args
    assert isinstance(status, StatusReport)
    assert status.island_id == 0
    assert status.first_line == 42
    assert status.coverage == 0.0
    assert status.covered is False


def test_maybe_report_marks_fully_covered_when_all_goals_covered(island_algorithm):
    channel = MagicMock()
    channel.drain_incoming.return_value = []
    goal = _fake_goal(1)
    island_algorithm.test_case_fitness_functions = [goal]
    extension = _bind(island_algorithm, channel, 0)
    island_algorithm._goals_manager.current_goals = []
    island_algorithm._archive.covered_goals = [goal]
    extension._pending_llm_covered.append(goal)
    code_object_meta = MagicMock()
    code_object_meta.code_object.co_firstlineno = 42
    island_algorithm.executor.subject_properties.existing_code_objects = {1: code_object_meta}

    extension.after_local_search(island_algorithm)

    (status,) = channel.report.call_args.args
    assert status.coverage == 1.0
    assert status.covered is True


def test_maybe_report_does_not_report_untouched_callable(island_algorithm):
    channel = MagicMock()
    channel.drain_incoming.return_value = []
    goal = _fake_goal(1)
    island_algorithm.test_case_fitness_functions = [goal]
    extension = _bind(island_algorithm, channel, 0)
    island_algorithm._goals_manager.current_goals = []
    island_algorithm._archive.covered_goals = []

    extension.after_local_search(island_algorithm)

    channel.report.assert_not_called()


def test_maybe_report_drains_incoming_and_updates_goals_manager(island_algorithm):
    channel = MagicMock()
    extension = _bind(island_algorithm, channel, 0)
    island_algorithm._goals_manager.current_goals = []
    island_algorithm._archive.covered_goals = []
    incoming_test_case = _FakeTestCase("def test_0():\n    pass\n")
    result = LLMWorkerResult(
        target_island=0,
        first_line=42,
        test_case=incoming_test_case,  # type: ignore[arg-type]
        content_hash="abc",
    )
    channel.drain_incoming.return_value = [result]

    extension.after_local_search(island_algorithm)

    assert len(island_algorithm._population) == 1
    assert island_algorithm._population[0].test_case is incoming_test_case
    island_algorithm._goals_manager.update.assert_called_once_with(island_algorithm._population)


def test_maybe_report_ingests_result_for_an_already_covered_goal_without_error(island_algorithm):
    channel = MagicMock()
    extension = _bind(island_algorithm, channel, 0)
    goal = _fake_goal(1)
    island_algorithm._goals_manager.current_goals = []
    island_algorithm._archive.covered_goals = [goal]
    stale_test_case = _FakeTestCase("def test_0():\n    pass\n")
    stale_result = LLMWorkerResult(
        target_island=0,
        first_line=42,
        test_case=stale_test_case,  # type: ignore[arg-type]
        content_hash="abc",
    )
    channel.drain_incoming.return_value = [stale_result]

    extension.after_local_search(island_algorithm)

    assert island_algorithm._population[0].test_case is stale_test_case
    island_algorithm._goals_manager.update.assert_called_once_with(island_algorithm._population)


def test_maybe_report_does_not_update_goals_manager_when_nothing_ingested(island_algorithm):
    channel = MagicMock()
    channel.drain_incoming.return_value = []
    extension = _bind(island_algorithm, channel, 0)
    island_algorithm._goals_manager.current_goals = []
    island_algorithm._archive.covered_goals = []

    extension.after_local_search(island_algorithm)

    island_algorithm._goals_manager.update.assert_not_called()


def test_maybe_report_incoming_chromosome_uses_own_test_factory_and_fitness_functions(
    island_algorithm,
):
    channel = MagicMock()
    extension = _bind(island_algorithm, channel, 0)
    island_algorithm._goals_manager.current_goals = []
    island_algorithm._archive.covered_goals = []
    own_fitness_function = MagicMock()
    own_fitness_function.is_maximisation_function.return_value = False
    island_algorithm.test_case_fitness_functions = [own_fitness_function]
    incoming_test_case = _FakeTestCase("def test_0():\n    pass\n")
    result = LLMWorkerResult(
        target_island=0,
        first_line=42,
        test_case=incoming_test_case,  # type: ignore[arg-type]
        content_hash="abc",
    )
    channel.drain_incoming.return_value = [result]

    extension.after_local_search(island_algorithm)

    chromosome = island_algorithm._population[0]
    assert isinstance(chromosome, tcc.TestCaseChromosome)
    assert chromosome.test_factory is island_algorithm.test_factory


def test_worker_results_do_not_write_the_archive(island_algorithm):
    channel = MagicMock()
    extension = _bind(island_algorithm, channel)
    island_algorithm._goals_manager.current_goals = []
    island_algorithm._archive.covered_goals = []
    island_algorithm._archive.reset_mock()
    channel.drain_incoming.return_value = [
        LLMWorkerResult(
            target_island=0,
            first_line=42,
            test_case=_FakeTestCase("def test_0():\n    pass\n"),  # type: ignore[arg-type]
            content_hash="abc",
        )
    ]

    extension.after_local_search(island_algorithm)

    assert island_algorithm._archive.update.call_count == 0
    assert island_algorithm._archive.add_goals.call_count == 0


def test_combined_island_updates_goals_from_migrants_before_the_worker_reports(
    monkeypatch, island_algorithm
):
    monkeypatch.setattr(
        config.configuration.island, "migration_strategy", config.MigrationStrategy.GOAL_TRIGGERED
    )
    events: list[str] = []
    unlocked_goal = _fake_goal(7)
    unlocked_goal.is_maximisation_function.return_value = False
    island_algorithm.test_case_fitness_functions = [unlocked_goal]
    island_algorithm._goals_manager.current_goals = []

    def _update(_population):
        events.append("goals_update")
        island_algorithm._goals_manager.current_goals = [unlocked_goal]

    island_algorithm._goals_manager.update.side_effect = _update
    island_algorithm._archive.covered_goals = []
    code_object_meta = MagicMock()
    code_object_meta.code_object.co_firstlineno = 70
    island_algorithm.executor.subject_properties.existing_code_objects = {7: code_object_meta}
    migrant = _FakeTestCase("def test_migrant():\n    pass\n")
    migration_channel = MagicMock()
    migration_channel.drain_incoming.return_value = [
        MigrationMessage(
            source_island=1,
            covered_goal=None,
            content_hash=compute_test_case_hash(migrant),  # type: ignore[arg-type]
            test_case=migrant,  # type: ignore[arg-type]
        )
    ]
    worker_channel = MagicMock()
    worker_channel.drain_incoming.return_value = []
    worker_channel.report.side_effect = lambda _status: events.append("report")
    island_algorithm.add_generation_extension(
        IslandMigrationExtension(0, migration_channel, island_algorithm)
    )
    worker_extension = _bind(island_algorithm, worker_channel)

    for extension in island_algorithm._generation_extensions:
        extension.after_local_search(island_algorithm)

    assert events == ["goals_update", "report"]
    (status,) = worker_channel.report.call_args.args
    assert status.first_line == 70
    assert worker_extension._last_seen_active_goals == island_algorithm.current_goals_snapshot()


def test_ingested_worker_results_are_logged(island_algorithm, caplog):
    channel = MagicMock()
    extension = _bind(island_algorithm, channel, 3)
    island_algorithm._goals_manager.current_goals = []
    island_algorithm._archive.covered_goals = []
    channel.drain_incoming.return_value = [
        LLMWorkerResult(
            target_island=3,
            first_line=42,
            test_case=_FakeTestCase("def test_0():\n    pass\n"),  # type: ignore[arg-type]
            content_hash="abc",
        )
    ]

    with caplog.at_level(logging.INFO, logger=llm_worker_algorithm.__name__):
        extension.after_local_search(island_algorithm)

    assert "Island 3 ingested 1 test case(s) from the LLM worker" in caplog.text


def test_nothing_is_logged_when_no_worker_result_arrives(island_algorithm, caplog):
    channel = MagicMock()
    channel.drain_incoming.return_value = []
    extension = _bind(island_algorithm, channel, 0)
    island_algorithm._goals_manager.current_goals = []
    island_algorithm._archive.covered_goals = []

    with caplog.at_level(logging.INFO, logger=llm_worker_algorithm.__name__):
        extension.after_local_search(island_algorithm)

    assert "ingested" not in caplog.text
