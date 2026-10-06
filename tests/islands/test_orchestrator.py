#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Tests for the island orchestrator."""

import os
import signal
import subprocess  # noqa: S404
import sys
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import multiprocess as mp
import pytest

import pynguin.configuration as config
import pynguin.generator as gen
import pynguin.utils.statistics.stats as stat
from pynguin.generator import ReturnCode
from pynguin.islands import orchestrator
from pynguin.islands.island import IslandResult
from pynguin.islands.migration_algorithm import MigrationStats
from pynguin.islands.orchestrator import run_pynguin_with_islands
from pynguin.utils.statistics.runtimevariable import RuntimeVariable

_CANNED_LLM_TEST_CASE_SOURCE = (
    'def test_llm_generated():\n    difficult_branches("not-a", 1337, 999)\n'
)


def _difficult_configuration(
    tmp_path: Path,
    *,
    num_islands: int,
    migration_strategy: config.MigrationStrategy,
    immigration_routing: config.ImmigrationRouting,
) -> config.Configuration:
    project_path = Path().absolute()
    if project_path.name == "tests":
        project_path /= ".."  # pragma: no cover
    project_path = project_path / "tests" / "fixtures" / "examples"
    return config.Configuration(
        algorithm=config.Algorithm.LLDYNAMOSA,
        stopping=config.StoppingConfiguration(maximum_search_time=3),
        module_name="difficult",
        test_case_output=config.TestCaseOutputConfiguration(output_path=str(tmp_path)),
        project_path=str(project_path),
        statistics_output=config.StatisticsOutputConfiguration(
            report_dir=str(tmp_path), statistics_backend=config.StatisticsBackend.NONE
        ),
        seeding=config.SeedingConfiguration(seed=1),
        island=config.IslandConfiguration(
            num_islands=num_islands, migration_strategy=migration_strategy
        ),
        llm_worker=config.LLMWorkerConfiguration(
            enabled=True, immigration_routing=immigration_routing
        ),
    )


def _base_configuration(tmp_path: Path) -> config.Configuration:
    project_path = Path().absolute()
    if project_path.name == "tests":
        project_path /= ".."  # pragma: no cover
    project_path = project_path / "docs" / "source" / "_static"
    return config.Configuration(
        algorithm=config.Algorithm.DYNAMOSA,
        stopping=config.StoppingConfiguration(maximum_search_time=2),
        module_name="example",
        test_case_output=config.TestCaseOutputConfiguration(output_path=str(tmp_path)),
        project_path=str(project_path),
        statistics_output=config.StatisticsOutputConfiguration(
            report_dir=str(tmp_path), statistics_backend=config.StatisticsBackend.NONE
        ),
        island=config.IslandConfiguration(num_islands=2),
    )


def test_fan_out_island_configs_gives_distinct_seeds_and_ids(tmp_path):
    base_configuration = _base_configuration(tmp_path)
    base_configuration.seeding.seed = 42
    base_configuration.island.num_islands = 3

    island_configs = orchestrator._fan_out_island_configs(base_configuration)

    assert len(island_configs) == 3
    assert [c.seeding.seed for c in island_configs] == [126, 127, 128]
    assert [c.island.island_id for c in island_configs] == [0, 1, 2]
    assert base_configuration.seeding.seed == 42
    assert base_configuration.island.island_id == -1


def test_fan_out_island_configs_gives_disjoint_seeds_for_consecutive_base_seeds(tmp_path):
    base_configuration = _base_configuration(tmp_path)
    base_configuration.island.num_islands = 8
    island_seeds = []
    for base_seed in range(10):
        base_configuration.seeding.seed = base_seed
        island_seeds.extend(
            c.seeding.seed for c in orchestrator._fan_out_island_configs(base_configuration)
        )

    assert len(island_seeds) == 80
    assert len(set(island_seeds)) == 80


def test_fan_out_island_configs_full_per_island_keeps_base_population(tmp_path):
    base_configuration = _base_configuration(tmp_path)
    base_configuration.island.num_islands = 3
    base_configuration.search_algorithm.population = 20

    island_configs = orchestrator._fan_out_island_configs(base_configuration)

    assert [c.search_algorithm.population for c in island_configs] == [20, 20, 20]


def test_fan_out_island_configs_fixed_total_distributed_splits_the_population(tmp_path):
    base_configuration = _base_configuration(tmp_path)
    base_configuration.island.num_islands = 3
    base_configuration.island.population_allocation = (
        config.PopulationAllocation.FIXED_TOTAL_DISTRIBUTED
    )
    base_configuration.search_algorithm.population = 20

    island_configs = orchestrator._fan_out_island_configs(base_configuration)

    sizes = [c.search_algorithm.population for c in island_configs]
    assert sizes == [7, 7, 6]
    assert sum(sizes) == 20


def test_fan_out_island_configs_does_not_alias_nested_fields(tmp_path):
    base_configuration = _base_configuration(tmp_path)

    island_configs = orchestrator._fan_out_island_configs(base_configuration)
    island_configs[0].seeding.seed = 111
    island_configs[1].seeding.seed = 222

    assert island_configs[0].seeding.seed != island_configs[1].seeding.seed
    assert island_configs[0].seeding is not island_configs[1].seeding


def test_fan_out_island_configs_switches_worker_islands_to_dynamosa_only_in_the_copies(tmp_path):
    base_configuration = _difficult_configuration(
        tmp_path,
        num_islands=3,
        migration_strategy=config.MigrationStrategy.DISABLED,
        immigration_routing=config.ImmigrationRouting.TARGETED,
    )

    island_configs = orchestrator._fan_out_island_configs(base_configuration)

    assert [c.algorithm for c in island_configs] == [config.Algorithm.DYNAMOSA] * 3
    assert base_configuration.algorithm is config.Algorithm.LLDYNAMOSA
    assert base_configuration.llm_worker.enabled is True


def test_fan_out_island_configs_keeps_the_algorithm_without_the_worker(tmp_path):
    base_configuration = _base_configuration(tmp_path)
    base_configuration.algorithm = config.Algorithm.MOSA

    island_configs = orchestrator._fan_out_island_configs(base_configuration)

    assert [c.algorithm for c in island_configs] == [config.Algorithm.MOSA] * 2


def test_run_pynguin_with_islands_merges_two_islands_into_one_suite(tmp_path):
    base_configuration = _base_configuration(tmp_path)
    gen.set_configuration(base_configuration)

    result = run_pynguin_with_islands(base_configuration)

    assert result == gen.ReturnCode.OK
    exported_files = list(tmp_path.glob("test_*.py"))
    assert len(exported_files) == 1
    assert "def test_" in exported_files[0].read_text()


def test_run_pynguin_with_islands_goal_triggered_migration_produces_valid_merged_suite(tmp_path):
    base_configuration = _base_configuration(tmp_path)
    base_configuration.island.num_islands = 3
    base_configuration.island.migration_strategy = config.MigrationStrategy.GOAL_TRIGGERED
    gen.set_configuration(base_configuration)

    result = run_pynguin_with_islands(base_configuration)

    assert result == gen.ReturnCode.OK
    exported_files = list(tmp_path.glob("test_*.py"))
    assert len(exported_files) == 1
    assert "def test_" in exported_files[0].read_text()


def test_run_pynguin_with_islands_llm_worker_targeted_delivers_llm_test(tmp_path):
    base_configuration = _difficult_configuration(
        tmp_path,
        num_islands=2,
        migration_strategy=config.MigrationStrategy.DISABLED,
        immigration_routing=config.ImmigrationRouting.TARGETED,
    )
    gen.set_configuration(base_configuration)

    with (
        patch("pynguin.large_language_model.client.require_api_key") as mock_key,
        patch("pynguin.large_language_model.llmagent.openai.OpenAI"),
        patch("pynguin.large_language_model.llmagent.openai.AsyncOpenAI"),
        patch(
            "pynguin.large_language_model.llmagent.LLMAgent.call_llm_for_uncovered_targets",
            return_value=_CANNED_LLM_TEST_CASE_SOURCE,
        ),
        patch(
            "pynguin.large_language_model.llmagent.LLMAgent.call_llm_for_uncovered_targets_async",
            new_callable=AsyncMock,
            return_value=_CANNED_LLM_TEST_CASE_SOURCE,
        ),
    ):
        mock_key.return_value = MagicMock()
        mock_key.return_value.get_secret_value.return_value = "test-api-key"
        result = run_pynguin_with_islands(base_configuration)

    assert result == gen.ReturnCode.OK
    exported_files = list(tmp_path.glob("test_*.py"))
    assert len(exported_files) == 1
    assert "1337" in exported_files[0].read_text()


def test_run_pynguin_with_islands_periodic_migration_produces_valid_merged_suite(tmp_path):
    base_configuration = _base_configuration(tmp_path)
    base_configuration.island.num_islands = 3
    base_configuration.island.migration_strategy = config.MigrationStrategy.PERIODIC
    base_configuration.island.periodic_migration_frequency = 1
    base_configuration.island.periodic_migration_size = 1
    gen.set_configuration(base_configuration)

    result = run_pynguin_with_islands(base_configuration)

    assert result == gen.ReturnCode.OK
    exported_files = list(tmp_path.glob("test_*.py"))
    assert len(exported_files) == 1
    assert "def test_" in exported_files[0].read_text()


def test_run_pynguin_with_islands_combined_migration_produces_valid_merged_suite(tmp_path):
    base_configuration = _base_configuration(tmp_path)
    base_configuration.island.num_islands = 3
    base_configuration.island.migration_strategy = config.MigrationStrategy.COMBINED
    base_configuration.island.periodic_migration_frequency = 1
    base_configuration.island.periodic_migration_size = 1
    gen.set_configuration(base_configuration)

    result = run_pynguin_with_islands(base_configuration)

    assert result == gen.ReturnCode.OK
    exported_files = list(tmp_path.glob("test_*.py"))
    assert len(exported_files) == 1
    assert "def test_" in exported_files[0].read_text()


def test_run_pynguin_with_islands_llm_worker_broadcast_reaches_all_islands(tmp_path):
    base_configuration = _difficult_configuration(
        tmp_path,
        num_islands=2,
        migration_strategy=config.MigrationStrategy.GOAL_TRIGGERED,
        immigration_routing=config.ImmigrationRouting.BROADCAST,
    )
    gen.set_configuration(base_configuration)

    with (
        patch("pynguin.large_language_model.client.require_api_key") as mock_key,
        patch("pynguin.large_language_model.llmagent.openai.OpenAI"),
        patch("pynguin.large_language_model.llmagent.openai.AsyncOpenAI"),
        patch(
            "pynguin.large_language_model.llmagent.LLMAgent.call_llm_for_uncovered_targets",
            return_value=_CANNED_LLM_TEST_CASE_SOURCE,
        ),
        patch(
            "pynguin.large_language_model.llmagent.LLMAgent.call_llm_for_uncovered_targets_async",
            new_callable=AsyncMock,
            return_value=_CANNED_LLM_TEST_CASE_SOURCE,
        ),
    ):
        mock_key.return_value = MagicMock()
        mock_key.return_value.get_secret_value.return_value = "test-api-key"
        result = run_pynguin_with_islands(base_configuration)

    assert result == gen.ReturnCode.OK
    exported_files = list(tmp_path.glob("test_*.py"))
    assert len(exported_files) == 1
    assert "1337" in exported_files[0].read_text()


def _ignore_sigterm_and_sleep():
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    time.sleep(60)


def test_stop_child_processes_kills_a_process_that_ignores_sigterm(monkeypatch):
    monkeypatch.setattr(orchestrator, "_TERMINATE_TIMEOUT_SECONDS", 0.5)
    process = mp.Process(target=_ignore_sigterm_and_sleep)
    process.start()
    time.sleep(0.5)

    orchestrator._stop_child_processes([process], manager=None)

    assert not process.is_alive()


def test_stop_child_processes_shuts_down_the_manager_before_waiting():
    events = []
    process = MagicMock()
    process.is_alive.side_effect = [True, False]
    process.terminate.side_effect = lambda: events.append("terminate")
    process.join.side_effect = lambda **_kwargs: events.append("join")
    manager = MagicMock()
    manager.shutdown.side_effect = lambda: events.append("manager shutdown")

    orchestrator._stop_child_processes([process], manager)

    assert events == ["terminate", "manager shutdown", "join"]


def test_stop_child_processes_skips_processes_that_were_never_started():
    process = MagicMock()
    process.pid = None
    manager = MagicMock()

    orchestrator._stop_child_processes([process], manager)

    process.terminate.assert_not_called()
    process.join.assert_not_called()
    manager.shutdown.assert_called_once()


def test_start_islands_tracks_each_island_before_starting_it(tmp_path, monkeypatch):
    processes_and_connections = []
    tracked_at_start = []

    def _fake_process(**_kwargs):
        process = MagicMock()
        process.start.side_effect = lambda: tracked_at_start.append(
            any(tracked is process for tracked, _ in processes_and_connections)
        )
        return process

    context = MagicMock()
    context.Process.side_effect = _fake_process
    monkeypatch.setattr(orchestrator.mp, "get_context", lambda _method: context)
    channels = orchestrator._ChannelSetup(None, {}, {}, None, None, None)

    orchestrator._start_islands(
        orchestrator._fan_out_island_configs(_base_configuration(tmp_path)),
        channels,
        (MagicMock(), MagicMock(), MagicMock()),
        processes_and_connections,
    )

    assert tracked_at_start == [True, True]


def test_start_llm_worker_starts_the_worker_and_closes_its_pipe_end():
    worker_process = MagicMock()
    sending_connection = MagicMock()
    channels = orchestrator._ChannelSetup(
        None, {}, {}, worker_process, MagicMock(), MagicMock(), sending_connection
    )

    orchestrator._start_llm_worker(channels)

    worker_process.start.assert_called_once()
    sending_connection.close.assert_called_once()
    assert channels.llm_worker_sending_connection is None


def _send_result(sending_connection):
    sending_connection.send("result")


def _exit_without_sending(_sending_connection):
    pass


def _start_with_pipe(target):
    receiving_connection, sending_connection = mp.Pipe(duplex=False)
    process = mp.get_context("fork").Process(target=target, args=(sending_connection,))
    process.start()
    sending_connection.close()
    return process, receiving_connection


def test_collect_island_result_returns_the_sent_result_and_joins_the_process():
    process, receiving_connection = _start_with_pipe(_send_result)

    result = orchestrator._collect_island_result(
        process, receiving_connection, time.monotonic() + 30
    )

    assert result == "result"
    assert not process.is_alive()


def test_collect_island_result_returns_none_when_the_island_dies_without_sending():
    process, receiving_connection = _start_with_pipe(_exit_without_sending)

    result = orchestrator._collect_island_result(
        process, receiving_connection, time.monotonic() + 30
    )

    assert result is None
    assert not process.is_alive()


def test_collect_island_result_stops_a_hung_island_at_the_deadline(monkeypatch):
    monkeypatch.setattr(orchestrator, "_TERMINATE_TIMEOUT_SECONDS", 0.5)
    process, receiving_connection = _start_with_pipe(
        lambda _connection: _ignore_sigterm_and_sleep()
    )
    started = time.monotonic()

    result = orchestrator._collect_island_result(process, receiving_connection, started + 0.5)

    assert result is None
    assert not process.is_alive()
    assert time.monotonic() - started < 10


def test_collect_llm_worker_result_stops_a_hung_worker(monkeypatch):
    monkeypatch.setattr(orchestrator, "_RESULT_GRACE_SECONDS", 0.5)
    monkeypatch.setattr(orchestrator, "_TERMINATE_TIMEOUT_SECONDS", 0.5)
    process, receiving_connection = _start_with_pipe(
        lambda _connection: _ignore_sigterm_and_sleep()
    )

    result = orchestrator._collect_llm_worker_result(process, receiving_connection)

    assert result is None
    assert not process.is_alive()


def _process_group_is_empty(process_group_id: int) -> bool:
    try:
        os.killpg(process_group_id, 0)
    except ProcessLookupError:
        return True
    return False


@pytest.mark.skip(reason="Flaky in CI under heavy load, see issue #320")
def test_sigterm_to_the_orchestrator_stops_all_island_and_worker_processes(tmp_path):
    project_path = Path().absolute()
    if project_path.name == "tests":
        project_path /= ".."  # pragma: no cover
    log_path = tmp_path / "run.log"
    environment = {
        **os.environ,
        "PYNGUIN_DANGER_AWARE": "1",
        "PYNGUIN_LLM_BASE_URL": "http://127.0.0.1:9/v1",
        "PYNGUIN_OPENAI_API_KEY": "offline-dummy",
    }
    command = [
        sys.executable,
        "-m",
        "pynguin",
        "--project-path",
        str(project_path / "tests" / "fixtures" / "examples"),
        "--module-name",
        "impossible",
        "--output-path",
        str(tmp_path / "out"),
        "--report-dir",
        str(tmp_path / "report"),
        "--algorithm",
        "LLDYNAMOSA",
        "--model_name",
        "offline-model",
        "--island.num_islands",
        "2",
        "--island.migration_strategy",
        "GOAL_TRIGGERED",
        "--llm_worker.enabled",
        "True",
        "--maximum_search_time",
        "60",
        "--max_retries",
        "1",
        "-v",
        "--no-rich",
    ]
    with log_path.open("w") as log_file:
        run = subprocess.Popen(  # noqa: S603
            command,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            env=environment,
            start_new_session=True,
        )
    started_messages = (
        "Island 0 process started",
        "Island 1 process started",
        "LLM worker process started",
    )
    try:
        deadline = time.time() + 60
        while (
            not all(message in log_path.read_text() for message in started_messages)
            and time.time() < deadline
        ):
            time.sleep(0.5)
        assert all(message in log_path.read_text() for message in started_messages)

        run.send_signal(signal.SIGTERM)
        run.wait(timeout=30)
        deadline = time.time() + 15
        while not _process_group_is_empty(run.pid) and time.time() < deadline:
            time.sleep(0.2)

        assert _process_group_is_empty(run.pid)
        log = log_path.read_text()
        assert "Island run interrupted" in log
        assert "Island 0 process interrupted" in log
        assert "Island 1 process interrupted" in log
        assert "LLM worker process interrupted" in log
        assert "did not stop after SIGTERM" not in log
    finally:
        if not _process_group_is_empty(run.pid):
            os.killpg(run.pid, signal.SIGKILL)  # pragma: no cover


def test_report_coverage_timeline_adds_the_best_coverage_so_far_across_islands():
    results = [
        IslandResult(
            0, [], ReturnCode.OK, coverage_timeline=[(1_000_000_000, 0.5), (3_000_000_000, 0.6)]
        ),
        IslandResult(
            1, [], ReturnCode.OK, coverage_timeline=[(2_000_000_000, 0.4), (4_000_000_000, 0.9)]
        ),
    ]

    orchestrator._report_coverage_timeline(results)

    assert stat.get_sequence_samples(RuntimeVariable.CoverageTimeline) == [
        (1_000_000_000, 0.5),
        (2_000_000_000, 0.5),
        (3_000_000_000, 0.6),
        (4_000_000_000, 0.9),
    ]


def test_report_search_effort_sums_iterations_and_takes_the_longest_search_time():
    results = [
        IslandResult(0, [], ReturnCode.OK, algorithm_iterations=40, search_time_ns=5_000),
        IslandResult(1, [], ReturnCode.OK, algorithm_iterations=35, search_time_ns=7_000),
    ]

    orchestrator._report_search_effort(results)

    tracked = dict(stat.statistics_tracker.variables_generator)
    assert tracked[RuntimeVariable.AlgorithmIterations] == 75
    assert tracked[RuntimeVariable.SearchTime] == 7_000


def test_report_search_effort_tracks_zero_without_island_results():
    orchestrator._report_search_effort([])

    tracked = dict(stat.statistics_tracker.variables_generator)
    assert tracked[RuntimeVariable.AlgorithmIterations] == 0
    assert tracked[RuntimeVariable.SearchTime] == 0


def test_report_migration_stats_tracks_totals_across_islands():
    results = [
        IslandResult(0, [], ReturnCode.OK, migration_stats=MigrationStats(3, 1, 2, 1)),
        IslandResult(1, [], ReturnCode.OK, migration_stats=MigrationStats(2, 4, 5, 0)),
        IslandResult(2, [], ReturnCode.OK),
    ]

    orchestrator._report_migration_stats(results)

    tracked = dict(stat.statistics_tracker.variables_generator)
    assert tracked[RuntimeVariable.MigrantsSentGoalTriggered] == 5
    assert tracked[RuntimeVariable.MigrantsSentPeriodic] == 5
    assert tracked[RuntimeVariable.MigrantsReceived] == 7
    assert tracked[RuntimeVariable.MigrantsDroppedAsDuplicate] == 1


def test_report_migration_stats_tracks_nothing_without_migration():
    results = [IslandResult(0, [], ReturnCode.OK), IslandResult(1, [], ReturnCode.OK)]

    orchestrator._report_migration_stats(results)

    assert dict(stat.statistics_tracker.variables_generator) == {}
