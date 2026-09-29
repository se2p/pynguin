#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides the entry point run by each island process."""

from __future__ import annotations

import dataclasses
import logging
import traceback
from typing import TYPE_CHECKING, cast

import multiprocess as mp

import pynguin.ga.generationalgorithmfactory as gaf
import pynguin.utils.statistics.statisticsobserver as sso
from pynguin import generator
from pynguin.ga.algorithms.dynamosaalgorithm import DynaMOSAAlgorithm
from pynguin.generator import ReturnCode, set_configuration
from pynguin.islands.llm_worker_algorithm import IslandLLMWorkerExtension
from pynguin.islands.migration_algorithm import IslandMigrationExtension
from pynguin.utils.exceptions import ConfigurationException
from pynguin.utils.logging_utils import WorkerFormatting

if TYPE_CHECKING:
    import multiprocess.connection as mp_conn

    import pynguin.configuration as config
    import pynguin.ga.coveragegoals as bg
    import pynguin.testcase.testcase as tc
    from pynguin.analyses.constants import ConstantProvider
    from pynguin.analyses.module import ModuleTestCluster
    from pynguin.ga.algorithms.generationalgorithm import GenerationAlgorithm
    from pynguin.islands.llm_worker_protocol import LLMWorkerChannel
    from pynguin.islands.migration import MigrationChannel
    from pynguin.islands.migration_algorithm import MigrationStats
    from pynguin.testcase.execution import TestCaseExecutor


_LOGGER = logging.getLogger(__name__)


@dataclasses.dataclass
class IslandTask:
    """Task to be executed by an island process."""

    island_id: int
    configuration: config.Configuration
    """The orchestrator must set a unique seed, island ID, and shared deadline
    before starting the island process. See ``orchestrator.py``.
    """

    migration_channel: MigrationChannel | None = None
    """Set by the orchestrator when migration is enabled.
    ``island_main()`` attaches migration to the island's search when it is set.
    """

    llm_worker_channel: LLMWorkerChannel | None = None
    """Set by the orchestrator when the LLM worker is enabled.
    ``island_main()`` attaches LLM-worker reporting and ingestion to the island's
    search when it is set.
    """


@dataclasses.dataclass
class IslandResult:
    """Result of one island's search, before any assertion generation or export."""

    island_id: int
    test_cases: list[tc.TestCase]
    return_code: ReturnCode
    covered_goals: list[bg.BranchGoal] = dataclasses.field(default_factory=list)
    """Goals covered by the island's final archive.
    Used for goal verification and migration or statistics logging across
    processes. The final merge itself deduplicates test cases by content.
    """

    coverage_samples: list[tuple[float, float]] = dataclasses.field(default_factory=list)
    """Coverage recorded after each generation as ``(elapsed_seconds, coverage)``.
    Used by the orchestrator to track per-island and merged coverage over time.
    """

    migration_stats: MigrationStats | None = None
    """Migration statistics recorded when migration is enabled.
    Includes sent, received, and duplicate-drop counts used by the orchestrator
    for migration logging.
    """


def _build_algorithm(
    task: IslandTask,
    executor: TestCaseExecutor,
    test_cluster: ModuleTestCluster,
    constant_provider: ConstantProvider,
) -> tuple[GenerationAlgorithm, IslandMigrationExtension | None]:
    """Build the search algorithm for an island.

    The algorithm always comes from the normal factory. Migration and LLM-worker
    integration, when their channels are present, are attached to it as generation
    extensions, migration first, so the worker's goal reporting sees goals that
    migrants just unlocked.

    Args:
        task: The island task and its optional communication channels.
        executor: The executor used by the algorithm.
        test_cluster: The test cluster used by the algorithm.
        constant_provider: The constant provider used by the algorithm.

    Returns:
        The configured search algorithm, and its migration extension if any.

    Raises:
        ConfigurationException: If channels are present but the island's
            algorithm is not plain DynaMOSA, whose loop runs extensions.
    """
    factory = gaf.TestSuiteGenerationAlgorithmFactory(executor, test_cluster, constant_provider)
    algorithm = factory.get_search_algorithm()
    if task.migration_channel is None and task.llm_worker_channel is None:
        return algorithm, None
    if type(algorithm) is not DynaMOSAAlgorithm:
        raise ConfigurationException(
            "Island migration and the LLM worker require the island to run DYNAMOSA, "
            f"got {type(algorithm).__name__}."
        )
    migration_extension = None
    if task.migration_channel is not None:
        migration_extension = IslandMigrationExtension(
            task.island_id, task.migration_channel, algorithm
        )
        algorithm.add_generation_extension(migration_extension)
    if task.llm_worker_channel is not None:
        algorithm.add_generation_extension(
            IslandLLMWorkerExtension(task.island_id, task.llm_worker_channel, algorithm)
        )
    return algorithm, migration_extension


def island_main(
    task: IslandTask,
    sending_connection: mp_conn.Connection,
) -> None:
    """Run test generation for a single island.

    The island performs its own setup and search, then sends the generated test
    cases and related search data back to the orchestrator. Final assertion
    generation and export are handled after the island results are merged.

    Args:
        task: The task assigned to the island.
        sending_connection: Connection used to send the result to the orchestrator.
    """
    try:
        with WorkerFormatting():
            _LOGGER.info(
                "Island %d process started (PID: %d)", task.island_id, mp.current_process().pid
            )
            set_configuration(task.configuration)
            _LOGGER.info(
                "Island %d population size %d",
                task.island_id,
                task.configuration.search_algorithm.population,
            )
            setup_result = generator._setup_and_check()  # noqa: SLF001
            if setup_result is None:
                sending_connection.send(IslandResult(task.island_id, [], ReturnCode.SETUP_FAILED))
                return
            executor, test_cluster, constant_provider = setup_result
            algorithm, migration_extension = _build_algorithm(
                task, executor, test_cluster, constant_provider
            )
            coverage_observer = sso.CoverageOverTimeObserver()
            algorithm.add_search_observer(coverage_observer)
            generation_result = algorithm.generate_tests()
            test_cases = [
                chromosome.test_case.clone()
                for chromosome in generation_result.test_case_chromosomes
            ]
            covered_goals = [
                cast("bg.BranchGoal", cast("bg.BranchCoverageTestFitness", target).goal)
                for target in algorithm.archive.covered_goals
            ]
            migration_stats = migration_extension.stats if migration_extension is not None else None
            sending_connection.send(
                IslandResult(
                    task.island_id,
                    test_cases,
                    ReturnCode.OK,
                    covered_goals,
                    coverage_observer.coverage_samples,
                    migration_stats,
                )
            )
            _LOGGER.info("Island %d completed with %d test cases", task.island_id, len(test_cases))
    except KeyboardInterrupt:
        _LOGGER.info("Island %d process interrupted", task.island_id)
    except Exception as e:  # noqa: BLE001
        _LOGGER.error(
            "Pynguin error in island %d process: %s\n%s", task.island_id, e, traceback.format_exc()
        )
        try:
            sending_connection.send(IslandResult(task.island_id, [], ReturnCode.SETUP_FAILED))
        except Exception:  # noqa: BLE001
            _LOGGER.error("Failed to send error result from island %d", task.island_id)
