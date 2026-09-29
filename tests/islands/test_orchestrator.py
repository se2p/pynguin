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

import pynguin.configuration as config
import pynguin.generator as gen
from pynguin.islands import orchestrator
from pynguin.islands.orchestrator import run_pynguin_with_islands

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

    island_configs = orchestrator._fan_out_island_configs(base_configuration, deadline_epoch_ns=999)

    assert len(island_configs) == 3
    assert [c.seeding.seed for c in island_configs] == [42, 43, 44]
    assert [c.island.island_id for c in island_configs] == [0, 1, 2]
    assert all(c.island.deadline_epoch_ns == 999 for c in island_configs)
    assert base_configuration.seeding.seed == 42
    assert base_configuration.island.island_id == -1


def test_fan_out_island_configs_full_per_island_keeps_base_population(tmp_path):
    base_configuration = _base_configuration(tmp_path)
    base_configuration.island.num_islands = 3
    base_configuration.search_algorithm.population = 20

    island_configs = orchestrator._fan_out_island_configs(base_configuration, deadline_epoch_ns=1)

    assert [c.search_algorithm.population for c in island_configs] == [20, 20, 20]


def test_fan_out_island_configs_fixed_total_distributed_splits_the_population(tmp_path):
    base_configuration = _base_configuration(tmp_path)
    base_configuration.island.num_islands = 3
    base_configuration.island.population_allocation = (
        config.PopulationAllocation.FIXED_TOTAL_DISTRIBUTED
    )
    base_configuration.search_algorithm.population = 20

    island_configs = orchestrator._fan_out_island_configs(base_configuration, deadline_epoch_ns=1)

    sizes = [c.search_algorithm.population for c in island_configs]
    assert sizes == [7, 7, 6]
    assert sum(sizes) == 20


def test_fan_out_island_configs_does_not_alias_nested_fields(tmp_path):
    base_configuration = _base_configuration(tmp_path)

    island_configs = orchestrator._fan_out_island_configs(base_configuration, deadline_epoch_ns=1)
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

    island_configs = orchestrator._fan_out_island_configs(base_configuration, deadline_epoch_ns=1)

    assert [c.algorithm for c in island_configs] == [config.Algorithm.DYNAMOSA] * 3
    assert base_configuration.algorithm is config.Algorithm.LLDYNAMOSA
    assert base_configuration.llm_worker.enabled is True


def test_fan_out_island_configs_keeps_the_algorithm_without_the_worker(tmp_path):
    base_configuration = _base_configuration(tmp_path)
    base_configuration.algorithm = config.Algorithm.MOSA

    island_configs = orchestrator._fan_out_island_configs(base_configuration, deadline_epoch_ns=1)

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


def _process_group_is_empty(process_group_id: int) -> bool:
    try:
        os.killpg(process_group_id, 0)
    except ProcessLookupError:
        return True
    return False


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
    try:
        deadline = time.time() + 60
        while "Island 1 process started" not in log_path.read_text() and time.time() < deadline:
            time.sleep(0.5)
        assert "Island 1 process started" in log_path.read_text()

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
