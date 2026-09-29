#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Tests for the island worker entry point."""

import importlib
import inspect
import pkgutil
import queue
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
from pynguin.ga.algorithms.dynamosaalgorithm import DynaMOSAAlgorithm
from pynguin.ga.algorithms.generationalgorithm import GenerationAlgorithm
from pynguin.ga.algorithms.lldynamosaalgorithm import LLDynaMOSAAlgorithm
from pynguin.ga.algorithms.llmosalgorithm import LLMOSAAlgorithm
from pynguin.ga.llmtestsuitechromosomefactory import LLMTestSuiteChromosomeFactory
from pynguin.ga.testcasechromosome import TestCaseChromosome
from pynguin.generator import ReturnCode
from pynguin.islands import island as island_module
from pynguin.islands import orchestrator
from pynguin.islands.island import IslandTask, island_main
from pynguin.islands.llm_worker_algorithm import IslandLLMWorkerExtension
from pynguin.islands.llm_worker_protocol import LLMWorkerChannel
from pynguin.islands.migration import MigrationChannel
from pynguin.islands.migration_algorithm import IslandMigrationExtension
from pynguin.utils.exceptions import ConfigurationException


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


def test_covered_goals_compare_equal_across_independently_instrumented_processes(tmp_path):
    for island_id in range(2):
        (tmp_path / str(island_id)).mkdir()
    tasks = [_island_task(island_id, tmp_path / str(island_id)) for island_id in range(2)]

    generator.set_configuration(tasks[0].configuration)
    generator._setup_and_check()

    processes_and_connections = []
    for task in tasks:
        receiving_connection, sending_connection = mp.Pipe(duplex=False)
        process = mp.Process(target=island_main, args=(task, sending_connection))
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


def _migration_channel(island_id: int) -> MigrationChannel:
    return MigrationChannel(island_id, {0: queue.Queue(), 1: queue.Queue()})


def _built_island(configuration, migration_channel=None, llm_worker_channel=None):
    generator.set_configuration(configuration)
    executor, test_cluster, constant_provider = generator._setup_and_check()
    task = IslandTask(0, configuration, migration_channel, llm_worker_channel)
    return island_module._build_algorithm(task, executor, test_cluster, constant_provider)


def test_island_classes_no_longer_exist():
    from pynguin.islands import llm_worker_algorithm, migration_algorithm  # noqa: PLC0415

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


def test_island_without_channels_runs_the_configured_algorithm_without_extensions(tmp_path):
    algorithm, migration_extension = _built_island(_island_task(0, tmp_path).configuration)

    assert type(algorithm) is DynaMOSAAlgorithm
    assert migration_extension is None
    assert algorithm._generation_extensions == []


def test_worker_island_is_plain_dynamosa_with_migration_then_worker(tmp_path):
    base_configuration = _island_task(0, tmp_path).configuration
    base_configuration.algorithm = config.Algorithm.LLDYNAMOSA
    base_configuration.island.migration_strategy = config.MigrationStrategy.GOAL_TRIGGERED
    base_configuration.llm_worker.enabled = True
    island_configuration = orchestrator._fan_out_island_configs(base_configuration, 1)[0]
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
    island_configuration = orchestrator._fan_out_island_configs(base_configuration, 1)[0]
    llm_channel = LLMWorkerChannel(0, queue.Queue(), queue.Queue())

    algorithm, _ = _built_island(island_configuration, None, llm_channel)
    population = algorithm._get_random_population()

    assert len(population) == 4
    assert all(isinstance(c, TestCaseChromosome) for c in population)
    assert seeding_calls == []


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
            if issubclass(cls, DynaMOSAAlgorithm) and cls is not DynaMOSAAlgorithm:
                subclasses.add(cls)

    assert subclasses == {LLDynaMOSAAlgorithm}
