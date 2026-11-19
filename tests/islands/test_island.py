#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Tests for the island worker entry point."""

import importlib
import inspect
import os
import pkgutil
import queue
import resource
import sys
import threading
import time
import types
from pathlib import Path
from unittest.mock import MagicMock

import multiprocess as mp
import pytest

import pynguin
import pynguin.configuration as config
import pynguin.ga.generationalgorithmfactory as gaf
import pynguin.ga.testcasechromosomefactory as tccf
import pynguin.islands
from pynguin import generator
from pynguin.analyses.constants import EmptyConstantProvider
from pynguin.ga.algorithms.dynamosaalgorithm import DynaMOSAAlgorithm
from pynguin.ga.algorithms.generationalgorithm import GenerationAlgorithm
from pynguin.ga.algorithms.lldynamosaalgorithm import LLDynaMOSAAlgorithm
from pynguin.ga.algorithms.llmosalgorithm import LLMOSAAlgorithm
from pynguin.ga.algorithms.mosaalgorithm import MOSAAlgorithm
from pynguin.ga.algorithms.wholesuitealgorithm import WholeSuiteAlgorithm
from pynguin.ga.llmtestsuitechromosomefactory import LLMTestSuiteChromosomeFactory
from pynguin.ga.testcasechromosome import TestCaseChromosome
from pynguin.generator import ReturnCode
from pynguin.islands import island as island_module
from pynguin.islands import orchestrator
from pynguin.islands.island import IslandTask, island_main
from pynguin.islands.llm_worker_algorithm import IslandLLMWorkerExtension
from pynguin.islands.llm_worker_protocol import LLMWorkerChannel
from pynguin.islands.migration import MigrationChannel, MigrationMessage, build_migration_channels
from pynguin.islands.migration_algorithm import IslandMigrationExtension
from pynguin.testcase.execution_result import ExecutionResult
from pynguin.utils.exceptions import ConfigurationException, TracingAbortedException


def _island_task(island_id: int, tmp_path: Path) -> IslandTask:
    project_path = Path().absolute()
    if project_path.name == "tests":
        project_path /= ".."  # pragma: no cover
    project_path = project_path / "docs" / "source" / "_static"
    configuration = config.Configuration(
        algorithm=config.Algorithm.DYNAMOSA,
        stopping=config.StoppingConfiguration(maximum_search_time=5),
        module_name="example",
        test_case_output=config.TestCaseOutputConfiguration(output_path=str(tmp_path)),
        project_path=str(project_path),
        statistics_output=config.StatisticsOutputConfiguration(
            report_dir=str(tmp_path), statistics_backend=config.StatisticsBackend.NONE
        ),
        seeding=config.SeedingConfiguration(seed=100 + island_id),
        island=config.IslandConfiguration(num_islands=2, island_id=island_id),
    )
    return IslandTask(island_id, configuration)


def test_covered_goals_compare_equal_across_islands_sharing_the_orchestrator_setup(
    tmp_path,
):
    for island_id in range(2):
        (tmp_path / str(island_id)).mkdir()
    tasks = [_island_task(island_id, tmp_path / str(island_id)) for island_id in range(2)]

    generator.set_configuration(tasks[0].configuration)
    setup_result = generator._setup_and_check()

    processes_and_connections = []
    for task in tasks:
        receiving_connection, sending_connection = mp.Pipe(duplex=False)
        process = mp.get_context("fork").Process(
            target=island_main, args=(task, sending_connection, setup_result)
        )
        process.start()
        sending_connection.close()
        processes_and_connections.append((process, receiving_connection))

    results = []
    for process, receiving_connection in processes_and_connections:
        results.append(receiving_connection.recv())
        process.join(timeout=30)

    result_a, result_b = results
    assert result_a.return_code == ReturnCode.OK
    assert result_b.return_code == ReturnCode.OK
    assert result_a.covered_goals
    assert set(result_a.covered_goals) == set(result_b.covered_goals)


def _island_result(tmp_path):
    task = _island_task(0, tmp_path)
    generator.set_configuration(task.configuration)
    setup_result = generator._setup_and_check()
    receiving_connection, sending_connection = mp.Pipe(duplex=False)
    process = mp.get_context("fork").Process(
        target=island_main, args=(task, sending_connection, setup_result)
    )
    process.start()
    sending_connection.close()

    result = receiving_connection.recv()
    process.join(timeout=30)
    return result


def test_island_reports_its_iterations_and_search_time(tmp_path):
    result = _island_result(tmp_path)

    assert result.return_code == ReturnCode.OK
    assert result.algorithm_iterations > 0
    assert result.search_time_ns > 0


def test_island_sends_the_execution_result_of_each_test_case(tmp_path):
    result = _island_result(tmp_path)

    assert result.test_cases
    assert len(result.execution_results) == len(result.test_cases)
    assert all(
        execution_result is not None and execution_result.execution_trace.executed_code_objects
        for execution_result in result.execution_results
    )


@pytest.mark.parametrize(("changed", "sent"), [(False, True), (True, False)])
def test_portable_last_execution_result_is_sent_only_for_an_unchanged_test_case(changed, sent):
    chromosome = TestCaseChromosome(MagicMock())
    chromosome.set_last_execution_result(ExecutionResult())
    chromosome.changed = changed

    assert (island_module._portable_last_execution_result(chromosome) is not None) is sent


def test_portable_last_execution_result_is_none_without_an_execution():
    chromosome = TestCaseChromosome(MagicMock())
    chromosome.changed = False

    assert island_module._portable_last_execution_result(chromosome) is None


def _migration_channel(island_id: int) -> MigrationChannel:
    return MigrationChannel(island_id, {0: queue.Queue(), 1: queue.Queue()})


def _built_island(configuration, migration_channel=None, llm_worker_channel=None):
    generator.set_configuration(configuration)
    executor, test_cluster, constant_provider = generator._setup_and_check()
    task = IslandTask(0, configuration, migration_channel, llm_worker_channel)
    return island_module._build_algorithm(task, executor, test_cluster, constant_provider)


def test_island_classes_no_longer_exist():
    from pynguin.islands import (  # noqa: PLC0415
        llm_worker_algorithm,
        migration_algorithm,
    )

    assert not hasattr(migration_algorithm, "_IslandDynaMOSAAlgorithm")
    assert not hasattr(migration_algorithm, "IslandMigrationMixin")
    assert not hasattr(llm_worker_algorithm, "_IslandLLDynaMOSAAlgorithm")
    assert not hasattr(llm_worker_algorithm, "IslandLLMWorkerMixin")


def test_islands_package_defines_no_search_algorithm_or_generation_loop():
    for module_info in pkgutil.iter_modules(pynguin.islands.__path__):
        module = importlib.import_module(f"pynguin.islands.{module_info.name}")
        for _name, cls in inspect.getmembers(module, inspect.isclass):
            if cls.__module__ != module.__name__:
                continue
            assert not issubclass(cls, GenerationAlgorithm), cls
            assert "generate_tests" not in vars(cls), cls


def test_parallel_dynamosa_island_is_plain_dynamosa_with_migration(tmp_path):
    configuration = _island_task(0, tmp_path).configuration
    configuration.island.migration_strategy = config.MigrationStrategy.COMBINED

    algorithm, migration_extension = _built_island(configuration, _migration_channel(0))

    assert type(algorithm) is DynaMOSAAlgorithm
    assert isinstance(migration_extension, IslandMigrationExtension)
    assert algorithm._generation_extensions == [migration_extension]
    assert type(algorithm).generate_tests is DynaMOSAAlgorithm.generate_tests


def test_island_without_channels_runs_the_configured_algorithm_without_extensions(
    tmp_path,
):
    algorithm, migration_extension = _built_island(_island_task(0, tmp_path).configuration)

    assert type(algorithm) is DynaMOSAAlgorithm
    assert migration_extension is None
    assert algorithm._generation_extensions == []


def test_worker_island_is_plain_dynamosa_with_migration_then_worker(tmp_path):
    base_configuration = _island_task(0, tmp_path).configuration
    base_configuration.algorithm = config.Algorithm.LLDYNAMOSA
    base_configuration.island.migration_strategy = config.MigrationStrategy.GOAL_TRIGGERED
    base_configuration.llm_worker.enabled = True
    island_configuration = orchestrator._fan_out_island_configs(base_configuration)[0]
    llm_channel = LLMWorkerChannel(0, queue.Queue(), queue.Queue())

    algorithm, migration_extension = _built_island(
        island_configuration, _migration_channel(0), llm_channel
    )

    assert base_configuration.algorithm is config.Algorithm.LLDYNAMOSA
    assert island_configuration.algorithm is config.Algorithm.DYNAMOSA
    assert type(algorithm) is DynaMOSAAlgorithm
    assert not isinstance(algorithm, LLMOSAAlgorithm)
    assert not hasattr(algorithm, "_maybe_intervene_on_stall")
    first, second = algorithm._generation_extensions
    assert first is migration_extension
    assert isinstance(second, IslandLLMWorkerExtension)
    assert not isinstance(algorithm._chromosome_factory, LLMTestSuiteChromosomeFactory)
    assert isinstance(algorithm._chromosome_factory, tccf.TestCaseChromosomeFactory)


def test_worker_island_initial_population_is_plain_test_cases_without_llm_seeding(
    tmp_path, monkeypatch
):
    seeding_calls = []
    monkeypatch.setattr(
        LLMTestSuiteChromosomeFactory,
        "_generate_llm_test_cases",
        lambda self: seeding_calls.append(self) or [],
    )
    base_configuration = _island_task(0, tmp_path).configuration
    base_configuration.algorithm = config.Algorithm.LLDYNAMOSA
    base_configuration.search_algorithm.population = 4
    base_configuration.llm_worker.enabled = True
    island_configuration = orchestrator._fan_out_island_configs(base_configuration)[0]
    llm_channel = LLMWorkerChannel(0, queue.Queue(), queue.Queue())

    algorithm, _ = _built_island(island_configuration, None, llm_channel)
    population = algorithm._get_random_population()

    assert len(population) == 4
    assert all(isinstance(c, TestCaseChromosome) for c in population)
    assert seeding_calls == []


@pytest.mark.parametrize(
    "algorithm_class", [MOSAAlgorithm, WholeSuiteAlgorithm, LLDynaMOSAAlgorithm]
)
def test_island_without_channels_accepts_any_algorithm(monkeypatch, algorithm_class):
    algorithm = object.__new__(algorithm_class)
    factory = MagicMock()
    factory.return_value.get_search_algorithm.return_value = algorithm
    monkeypatch.setattr(gaf, "TestSuiteGenerationAlgorithmFactory", factory)
    task = IslandTask(0, MagicMock())

    built_algorithm, migration_extension = island_module._build_algorithm(
        task, MagicMock(), MagicMock(), MagicMock()
    )

    assert built_algorithm is algorithm
    assert migration_extension is None


def test_island_extensions_are_refused_on_lldynamosa(monkeypatch):
    factory = MagicMock()
    factory.return_value.get_search_algorithm.return_value = object.__new__(LLDynaMOSAAlgorithm)
    monkeypatch.setattr(gaf, "TestSuiteGenerationAlgorithmFactory", factory)
    task = IslandTask(0, MagicMock(), _migration_channel(0), None)

    with pytest.raises(ConfigurationException, match="require the island to run DYNAMOSA"):
        island_module._build_algorithm(task, MagicMock(), MagicMock(), MagicMock())


def test_only_lldynamosa_subclasses_dynamosa_across_pynguin():
    subclasses = set()
    for module_info in pkgutil.walk_packages(pynguin.__path__, "pynguin."):
        try:
            module = importlib.import_module(module_info.name)
        except Exception:  # noqa: BLE001, S112
            continue
        for _name, cls in inspect.getmembers(module, inspect.isclass):
            if isinstance(cls, types.GenericAlias):
                continue
            try:
                if issubclass(cls, DynaMOSAAlgorithm) and cls is not DynaMOSAAlgorithm:
                    subclasses.add(cls)
            except TypeError:
                continue

    assert subclasses == {LLDynaMOSAAlgorithm}


def test_new_fds_from_hands_out_numbers_from_the_floor_only_inside_the_context():
    with island_module._new_fds_from(512) as beyond_floor:
        inside = os.open(os.devnull, os.O_RDONLY)
    outside = os.open(os.devnull, os.O_RDONLY)
    os.close(inside)
    os.close(outside)

    assert beyond_floor is True
    assert inside >= 512
    assert outside < 512


def test_new_fds_from_reports_when_the_open_file_limit_cannot_be_raised(monkeypatch):
    monkeypatch.setattr(resource, "getrlimit", lambda _resource: (64, 64))
    monkeypatch.setattr(resource, "setrlimit", MagicMock(side_effect=ValueError))

    with island_module._new_fds_from(512) as beyond_floor:
        fd = os.open(os.devnull, os.O_RDONLY)
    os.close(fd)

    assert beyond_floor is False
    assert fd < 512


def test_connection_fd_floor_starts_above_the_random_integers():
    assert island_module._connection_fd_floor(128, EmptyConstantProvider()) == 512


def test_connection_fd_floor_moves_past_constants_in_its_window():
    provider = MagicMock()
    provider.get_all_constants_for.return_value = [3, 512, 515, 600]

    assert island_module._connection_fd_floor(128, provider) == 516


def _island_whose_sut_closes_every_reachable_fd(task, sending_connection, floor):
    sending_connection = island_module._move_connections_beyond_sut_reach(
        task, sending_connection, EmptyConstantProvider()
    )
    os.closerange(3, floor)
    task.migration_channel.broadcast(MigrationMessage(0, None, "hash", "migrant"))  # type: ignore[arg-type]
    sending_connection.send(task.migration_channel.drain_incoming())


def test_island_connections_survive_the_sut_closing_every_fd_it_can_reach(tmp_path):
    task = _island_task(0, tmp_path)
    task.configuration.test_creation.max_int = 128
    floor = island_module._CONNECTION_FD_FLOOR_FACTOR * 128
    with mp.Manager() as manager:
        channels = build_migration_channels(2, manager)
        channels[1].broadcast(MigrationMessage(1, None, "peer-hash", "peer"))  # type: ignore[arg-type]
        task.migration_channel = channels[0]
        receiving_connection, sending_connection = mp.Pipe(duplex=False)
        process = mp.get_context("fork").Process(
            target=_island_whose_sut_closes_every_reachable_fd,
            args=(task, sending_connection, floor),
        )
        process.start()
        sending_connection.close()

        drained = receiving_connection.recv()
        process.join(timeout=30)

        assert [message.content_hash for message in drained] == ["peer-hash"]
        assert [message.content_hash for message in channels[1].drain_incoming()] == ["hash"]
        assert process.exitcode == 0


def _allocate_with_limited_data_size(task, sending_connection):
    with island_module._limited_data_size(task):
        try:
            " ".center(10**11)
        except MemoryError:
            outcome = "MemoryError"
        else:
            outcome = "allocated"
    sending_connection.send((outcome, len(" ".center(6 * 10**8))))


@pytest.mark.skipif(sys.platform != "linux", reason="Only Linux enforces RLIMIT_DATA")
def test_limited_data_size_turns_a_huge_allocation_into_a_memory_error(tmp_path):
    task = _island_task(0, tmp_path)
    task.configuration.stopping.maximum_memory = 512
    receiving_connection, sending_connection = mp.Pipe(duplex=False)
    process = mp.get_context("fork").Process(
        target=_allocate_with_limited_data_size, args=(task, sending_connection)
    )
    process.start()
    sending_connection.close()

    outcome = receiving_connection.recv()
    process.join(timeout=30)

    assert outcome == ("MemoryError", 6 * 10**8)


def test_data_size_is_limited_above_maximum_memory_during_the_search_only(tmp_path, monkeypatch):
    task = _island_task(0, tmp_path)
    task.configuration.stopping.maximum_memory = 512
    setrlimit = MagicMock()
    monkeypatch.setattr(resource, "getrlimit", lambda _resource: (7, resource.RLIM_INFINITY))
    monkeypatch.setattr(resource, "setrlimit", setrlimit)

    with island_module._limited_data_size(task):
        setrlimit.assert_called_once_with(
            resource.RLIMIT_DATA, (2 * 512 * 1024 * 1024, resource.RLIM_INFINITY)
        )

    setrlimit.assert_called_with(resource.RLIMIT_DATA, (7, resource.RLIM_INFINITY))


def test_data_size_stays_unlimited_without_a_maximum_memory(tmp_path, monkeypatch):
    task = _island_task(0, tmp_path)
    task.configuration.stopping.maximum_memory = -1
    setrlimit = MagicMock()
    monkeypatch.setattr(resource, "setrlimit", setrlimit)

    with island_module._limited_data_size(task):
        pass

    setrlimit.assert_not_called()


def _write_topology(root: Path, cores: dict[int, int]) -> None:
    for cpu, core in cores.items():
        topology = root / f"cpu{cpu}" / "topology"
        topology.mkdir(parents=True)
        (topology / "physical_package_id").write_text("0\n")
        (topology / "core_id").write_text(f"{core}\n")


def test_first_cpu_per_core_takes_one_hardware_thread_of_each_core(tmp_path, monkeypatch):
    _write_topology(tmp_path, {1: 1, 3: 3, 25: 1, 27: 3})
    monkeypatch.setattr(os, "sched_getaffinity", lambda _pid: {27, 1, 25, 3}, raising=False)

    assert island_module._first_cpu_per_core(tmp_path) == [1, 3]


def test_first_cpu_per_core_is_unknown_without_a_topology(tmp_path, monkeypatch):
    monkeypatch.setattr(os, "sched_getaffinity", lambda _pid: {0, 1}, raising=False)

    assert island_module._first_cpu_per_core(tmp_path) is None


def test_first_cpu_per_core_is_unknown_without_cpu_affinity(tmp_path, monkeypatch):
    monkeypatch.delattr(os, "sched_getaffinity", raising=False)

    assert island_module._first_cpu_per_core(tmp_path) is None


@pytest.mark.parametrize("island_id", [0, 1])
def test_island_is_pinned_to_its_own_core(tmp_path, monkeypatch, island_id):
    monkeypatch.setattr(island_module, "_first_cpu_per_core", lambda: [1, 3])
    sched_setaffinity = MagicMock()
    monkeypatch.setattr(os, "sched_setaffinity", sched_setaffinity, raising=False)

    island_module._pin_to_own_core(_island_task(island_id, tmp_path))

    sched_setaffinity.assert_called_once_with(0, {[1, 3][island_id]})


@pytest.mark.parametrize("cpus", [None, [1]])
def test_island_is_not_pinned_without_a_core_per_island(tmp_path, monkeypatch, cpus):
    monkeypatch.setattr(island_module, "_first_cpu_per_core", lambda: cpus)
    sched_setaffinity = MagicMock()
    monkeypatch.setattr(os, "sched_setaffinity", sched_setaffinity, raising=False)

    island_module._pin_to_own_core(_island_task(0, tmp_path))

    sched_setaffinity.assert_not_called()


def test_search_error_without_a_settable_data_size_is_not_chained_to_it(tmp_path, monkeypatch):
    monkeypatch.setattr(resource, "setrlimit", MagicMock(side_effect=ValueError))

    with (
        pytest.raises(KeyError) as error_info,
        island_module._limited_data_size(_island_task(0, tmp_path)),
    ):
        raise KeyError

    assert error_info.value.__context__ is None


class _WaitsInFinalizer:
    def __init__(self, lock):
        self._lock = lock

    def __del__(self):
        with self._lock:
            pass


@pytest.mark.filterwarnings("ignore::pytest.PytestUnraisableExceptionWarning")
def test_overrun_interrupt_releases_a_finalizer_waiting_for_a_lock_left_held(monkeypatch):
    monkeypatch.setattr(island_module, "_SEARCH_OVERRUN_GRACE_SECONDS", 0)
    lock = threading.Lock()
    lock.acquire()
    searched_on = False

    with island_module._interrupting_overrun(0.1):
        _WaitsInFinalizer(lock)
        searched_on = True

    assert searched_on


def test_overrun_interrupt_ends_a_search_waiting_outside_a_finalizer(monkeypatch):
    monkeypatch.setattr(island_module, "_SEARCH_OVERRUN_GRACE_SECONDS", 0)
    lock = threading.Lock()
    lock.acquire()

    with (
        pytest.raises(island_module._SearchOverrunError),
        island_module._interrupting_overrun(0.1),
    ):
        lock.acquire()


def test_search_within_its_time_is_not_interrupted():
    with island_module._interrupting_overrun(60):
        time.sleep(0.2)


@pytest.mark.parametrize(
    "error",
    [
        MemoryError(),
        RuntimeError("can't start new thread"),
        island_module._SearchOverrunError(),
    ],
)
def test_search_ending_early_returns_its_archive(tmp_path, error):
    task = _island_task(0, tmp_path)
    task.configuration.stopping.maximum_memory = -1
    algorithm = MagicMock()
    algorithm.generate_tests.side_effect = error

    result = island_module._search(task, algorithm)

    algorithm.after_search_finish.assert_called_once_with()
    algorithm.create_test_suite.assert_called_once_with(algorithm.archive.solutions)
    assert result is algorithm.create_test_suite.return_value


def test_search_ending_early_survives_a_logging_handler_of_the_sut(tmp_path, monkeypatch):
    task = _island_task(0, tmp_path)
    task.configuration.stopping.maximum_memory = -1
    algorithm = MagicMock()
    algorithm.generate_tests.side_effect = island_module._SearchOverrunError()
    logger = MagicMock()
    logger.warning.side_effect = TracingAbortedException("aborted")
    monkeypatch.setattr(island_module, "_LOGGER", logger)

    result = island_module._search(task, algorithm)

    logger.warning.assert_called_once()
    algorithm.create_test_suite.assert_called_once_with(algorithm.archive.solutions)
    assert result is algorithm.create_test_suite.return_value


def test_search_failing_otherwise_raises(tmp_path):
    task = _island_task(0, tmp_path)
    task.configuration.stopping.maximum_memory = -1
    algorithm = MagicMock()
    algorithm.generate_tests.side_effect = RuntimeError("broken")

    with pytest.raises(RuntimeError, match="broken"):
        island_module._search(task, algorithm)

    algorithm.create_test_suite.assert_not_called()
