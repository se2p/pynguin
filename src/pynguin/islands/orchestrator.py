#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides the island orchestrator: spawns islands, waits, merges their results."""

from __future__ import annotations

import copy
import dataclasses
import logging
import signal
import threading
import time
from typing import TYPE_CHECKING, Any

import multiprocess as mp

import pynguin.configuration as config
import pynguin.utils.statistics.stats as stat
from pynguin.generator import ReturnCode
from pynguin.islands.aggregation import assemble_final_suite, prepare_orchestrator_setup
from pynguin.islands.island import IslandResult, IslandTask, island_main
from pynguin.islands.llm_worker import LLMWorkerTask, llm_worker_main
from pynguin.islands.llm_worker_protocol import build_llm_worker_channels
from pynguin.islands.migration import MigrationChannel, build_migration_inboxes
from pynguin.islands.migration_algorithm import MigrationStats
from pynguin.islands.population_allocation import compute_island_population_size
from pynguin.utils.statistics.runtimevariable import RuntimeVariable

if TYPE_CHECKING:
    import types

    import multiprocess.connection as mp_conn
    import multiprocess.managers as mp_managers

    from pynguin.analyses.constants import ConstantProvider
    from pynguin.analyses.module import ModuleTestCluster
    from pynguin.islands.llm_worker_protocol import LLMWorkerChannel, WorkerStatsReport
    from pynguin.testcase.execution import TestCaseExecutor

_LOGGER = logging.getLogger(__name__)

# Maximum time to wait for an island process to terminate. This timeout prevents
# the orchestrator from blocking indefinitely if an island does not shut down
# cleanly. It is independent of the search budget.
_JOIN_TIMEOUT_SECONDS = 30

# Maximum time an interrupted island or LLM worker gets to exit before it is killed.
_TERMINATE_TIMEOUT_SECONDS = 5

# Maximum time, beyond the search budget, the islands get to send their results.
# An island checks its stopping conditions only between generations, so it may
# overrun the budget by up to one generation. The LLM worker gets the same time to
# send its stats after it was told to stop, since it first finishes in-flight
# queries. A process that misses this deadline is considered hung and is stopped.
_RESULT_GRACE_SECONDS = 300

# Islands and the LLM worker are forked so they inherit the orchestrator's SUT
# setup: the instrumented SUT, the test cluster, and the executor. These cannot be
# pickled, and the test cluster's callables compare by identity, so a spawned
# process would have to redo the whole setup instead. generator._verify_config()
# rejects island mode on platforms without fork.
_FORK_START_METHOD = "fork"


def _fan_out_island_configs(
    base_configuration: config.Configuration,
) -> list[config.Configuration]:
    """Create an independent configuration for each island.

    Each island gets its own island ID and the seed
    ``base_seed * num_islands + island_id``. Runs with consecutive base seeds, e.g.
    the repetitions of an experiment, thus use disjoint blocks of island seeds, so
    no two of their islands start from the same random state. For worker-enabled
    runs, the island configuration uses DYNAMOSA while the base configuration
    remains LLDYNAMOSA.

    Args:
        base_configuration: Configuration used as the template for each island.

    Returns:
        One independent Configuration per island without modifying the base.
    """
    base_seed = base_configuration.seeding.seed
    base_population = base_configuration.search_algorithm.population
    num_islands = base_configuration.island.num_islands
    allocation = base_configuration.island.population_allocation
    island_configs = []
    for island_id in range(num_islands):
        island_config = copy.deepcopy(base_configuration)
        island_config.seeding.seed = base_seed * num_islands + island_id
        island_config.island.island_id = island_id
        if base_configuration.llm_worker.enabled:
            island_config.algorithm = config.Algorithm.DYNAMOSA
        island_config.search_algorithm.population = compute_island_population_size(
            base_population, allocation, num_islands, island_id
        )
        island_configs.append(island_config)
    return island_configs


@dataclasses.dataclass
class _ChannelSetup:
    """Bundles everything run_pynguin_with_islands() needs from channel setup."""

    manager: mp_managers.SyncManager | None
    migration_channels: dict[int, MigrationChannel]
    llm_channels: dict[int, LLMWorkerChannel]
    llm_worker_process: mp.Process | None
    llm_worker_connection: mp_conn.Connection | None
    llm_status_queue: mp_managers.BaseProxy | None
    llm_worker_sending_connection: mp_conn.Connection | None = None
    """The LLM worker's end of its stats pipe; closed here once the worker started."""


def _setup_channels(
    base_configuration: config.Configuration, test_cluster: ModuleTestCluster
) -> _ChannelSetup:
    """Builds the shared Manager and migration/LLM-worker channels, if needed.

    Also creates the LLM worker process, if enabled, but does not start it:
    _start_llm_worker() does, once the caller holds the returned setup, so an
    interruption can always stop the worker.

    Args:
        base_configuration: The configuration the run started from.
        test_cluster: The orchestrator's test cluster, handed to the LLM worker.

    Returns:
        Everything the caller needs to wire into IslandTasks and shut down later.
    """
    num_islands = base_configuration.island.num_islands
    migration_active = (
        base_configuration.island.migration_strategy is not config.MigrationStrategy.DISABLED
    )
    manager = mp.Manager() if migration_active or base_configuration.llm_worker.enabled else None
    migration_inboxes = (
        build_migration_inboxes(num_islands, manager)
        if manager is not None and migration_active
        else None
    )
    migration_channels = (
        {
            island_id: MigrationChannel(island_id, migration_inboxes)
            for island_id in range(num_islands)
        }
        if migration_inboxes is not None
        else {}
    )

    if not base_configuration.llm_worker.enabled:
        return _ChannelSetup(manager, migration_channels, {}, None, None, None)

    status_queue, result_inboxes, llm_channels = build_llm_worker_channels(num_islands, manager)
    broadcast_inboxes = (
        migration_inboxes
        if base_configuration.llm_worker.immigration_routing is config.ImmigrationRouting.BROADCAST
        else None
    )
    worker_task = LLMWorkerTask(
        configuration=base_configuration,
        status_queue=status_queue,
        result_inboxes=result_inboxes,
        broadcast_inboxes=broadcast_inboxes,
    )
    llm_worker_connection, worker_sending_connection = mp.Pipe(duplex=False)
    llm_worker_process = mp.get_context(_FORK_START_METHOD).Process(
        target=llm_worker_main,
        args=(worker_task, worker_sending_connection, test_cluster),
        name="PynguinLLMWorker",
    )
    return _ChannelSetup(
        manager,
        migration_channels,
        llm_channels,
        llm_worker_process,
        llm_worker_connection,
        status_queue,
        worker_sending_connection,
    )


def _start_llm_worker(setup: _ChannelSetup) -> None:
    """Starts the LLM worker process, if enabled.

    It must already be running to receive status reports once islands start.

    Args:
        setup: The channel setup returned by _setup_channels().
    """
    if setup.llm_worker_process is None or setup.llm_worker_sending_connection is None:
        return
    setup.llm_worker_process.start()
    setup.llm_worker_sending_connection.close()
    setup.llm_worker_sending_connection = None


def _shutdown_llm_worker(setup: _ChannelSetup) -> None:
    """Signals the LLM worker to stop, collects its stats, and tracks them.

    Args:
        setup: The channel setup returned by _setup_channels().
    """
    if setup.llm_worker_process is None or setup.llm_status_queue is None:
        return
    setup.llm_status_queue.put(None)
    stats_report = _collect_llm_worker_result(setup.llm_worker_process, setup.llm_worker_connection)
    if stats_report is not None:
        _track_llm_worker_stats(stats_report)


def run_pynguin_with_islands(base_configuration: config.Configuration) -> ReturnCode:
    """Run test generation across multiple islands and merge the results.

    Args:
        base_configuration: The configuration used to create each island.
            num_islands must be > 1.

    Returns:
        The final merged generation result.
    """
    # Set up the SUT once, before starting islands: the forked islands and LLM
    # worker inherit it, and the islands' TestCases can be unpickled here later.
    setup_result = prepare_orchestrator_setup(base_configuration)
    if setup_result is None:
        return ReturnCode.SETUP_FAILED
    executor, test_cluster, constant_provider = setup_result

    island_configs = _fan_out_island_configs(base_configuration)

    previous_sigterm_handler = _install_sigterm_as_keyboard_interrupt()
    channels: _ChannelSetup | None = None
    processes_and_connections: list[tuple[mp.Process, mp_conn.Connection]] = []
    try:
        channels = _setup_channels(base_configuration, test_cluster)
        _start_llm_worker(channels)
        # The islands start searching right after they are started, so their
        # CoverageTimeline time stamps are relative to about this moment.
        stat.set_sequence_start_time(time.time_ns())
        _start_islands(island_configs, channels, setup_result, processes_and_connections)
        result_deadline = (
            time.monotonic()
            + base_configuration.stopping.maximum_search_time
            + _RESULT_GRACE_SECONDS
        )

        results = [
            result
            for process, receiving_connection in processes_and_connections
            if (result := _collect_island_result(process, receiving_connection, result_deadline))
            is not None
        ]

        _shutdown_llm_worker(channels)
    except KeyboardInterrupt:
        child_processes = [process for process, _ in processes_and_connections]
        if channels is not None and channels.llm_worker_process is not None:
            child_processes.append(channels.llm_worker_process)
        _LOGGER.info(
            "Island run interrupted; stopping %d island and LLM worker process(es)",
            len(child_processes),
        )
        _stop_child_processes(child_processes, channels.manager if channels is not None else None)
        if channels is not None:
            channels.manager = None
        raise
    finally:
        if channels is not None and channels.manager is not None:
            channels.manager.shutdown()
        _restore_sigterm_handler(previous_sigterm_handler)

    _report_coverage_timeline(results)
    _report_search_effort(results)
    _report_migration_stats(results)

    return assemble_final_suite(results, executor, test_cluster, constant_provider)


def _start_islands(
    island_configs: list[config.Configuration],
    channels: _ChannelSetup,
    setup_result: tuple[TestCaseExecutor, ModuleTestCluster, ConstantProvider],
    processes_and_connections: list[tuple[mp.Process, mp_conn.Connection]],
) -> None:
    """Starts one process per island configuration.

    Each process is appended to processes_and_connections before it is started:
    a started island can log and be seen as running at once, so an interruption
    right after its start must already find it there to stop it.

    Args:
        island_configs: One configuration per island.
        channels: The migration and LLM-worker channels to hand to the islands.
        setup_result: The orchestrator's SUT setup, inherited by each island.
        processes_and_connections: Receives each island process and its result pipe.
    """
    for island_config in island_configs:
        receiving_connection, sending_connection = mp.Pipe(duplex=False)
        island_id = island_config.island.island_id
        task = IslandTask(
            island_id,
            island_config,
            channels.migration_channels.get(island_id),
            channels.llm_channels.get(island_id),
        )
        process = mp.get_context(_FORK_START_METHOD).Process(
            target=island_main,
            args=(task, sending_connection, setup_result),
            name=f"PynguinIsland-{island_id}",
        )
        processes_and_connections.append((process, receiving_connection))
        process.start()
        sending_connection.close()


def _raise_keyboard_interrupt(_signum: int, _frame: types.FrameType | None) -> None:
    raise KeyboardInterrupt


def _install_sigterm_as_keyboard_interrupt() -> Any:
    """Makes SIGTERM stop the island run the same way Ctrl+C does.

    Island, LLM-worker and Manager processes are forked afterward and inherit the
    handler, so a SIGTERM sent to any of them, or only to the orchestrator, ends in
    the same orderly shutdown as a KeyboardInterrupt.

    Returns:
        The previous SIGTERM handler, or None when not called from the main thread,
        where Python does not allow installing signal handlers.
    """
    if threading.current_thread() is not threading.main_thread():
        return None
    return signal.signal(signal.SIGTERM, _raise_keyboard_interrupt)


def _restore_sigterm_handler(previous_handler: Any) -> None:
    """Restores the SIGTERM handler that was active before the island run.

    Args:
        previous_handler: The value returned by _install_sigterm_as_keyboard_interrupt().
    """
    if previous_handler is not None:
        signal.signal(signal.SIGTERM, previous_handler)


def _stop_child_processes(
    processes: list[mp.Process], manager: mp_managers.SyncManager | None
) -> None:
    """Stops child processes and the Manager, killing processes that do not exit in time.

    The Manager is shut down after the processes were signalled and before
    waiting for them: the LLM worker waits for status reports on a Manager queue
    in a helper thread, and can only exit once that queue is gone.

    Processes are tracked before they are started, so an interruption during
    start-up can pass processes that were never started; those are skipped.

    Args:
        processes: The island and LLM-worker processes to stop.
        manager: The Manager owning the channels, if any.
    """
    started = [process for process in processes if process.pid is not None]
    for process in started:
        if process.is_alive():
            process.terminate()
    if manager is not None:
        manager.shutdown()
    for process in started:
        _join_or_kill(process)


def _join_or_kill(process: mp.Process) -> None:
    """Waits for a terminated process to exit, killing it if it does not exit in time.

    SIGTERM is turned into a KeyboardInterrupt, which a process stuck in native
    code only handles once it returns to Python, so SIGKILL is the fallback.

    Args:
        process: The process that was sent SIGTERM.
    """
    process.join(timeout=_TERMINATE_TIMEOUT_SECONDS)
    if process.is_alive():
        _LOGGER.error("Process %s did not stop after SIGTERM, killing it", process.name)
        process.kill()
        process.join()


def _report_coverage_timeline(results: list[IslandResult]) -> None:
    """Merges the islands' CoverageTimelines into the orchestrator's one.

    Each island records the standard CoverageTimeline in its own process, which
    never writes statistics. The merged curve is the best coverage any island has
    reached so far, a lower bound of the merged suite's coverage at that time. The
    final merged suite's coverage is added after it when the result is finalized.

    Args:
        results: One IslandResult per island.
    """
    for result in results:
        _LOGGER.info(
            "Island %d coverage over time (s, coverage): %s",
            result.island_id,
            [
                (time_stamp / 1_000_000_000, coverage)
                for time_stamp, coverage in result.coverage_timeline
            ],
        )

    merged_samples = sorted(sample for result in results for sample in result.coverage_timeline)
    best_so_far = 0.0
    merged_timeline = []
    for time_stamp, coverage in merged_samples:
        best_so_far = max(best_so_far, coverage)
        merged_timeline.append((time_stamp, best_so_far))
    _LOGGER.info(
        "Best coverage across all islands over time (s, coverage): %s",
        [(time_stamp / 1_000_000_000, coverage) for time_stamp, coverage in merged_timeline],
    )
    stat.add_sequence_samples(RuntimeVariable.CoverageTimeline, merged_timeline)


def _report_search_effort(results: list[IslandResult]) -> None:
    """Tracks the island search's generations and wall-clock time as output variables.

    AlgorithmIterations is the number of generations all islands ran together.
    SearchTime is the longest island search time, since the islands search
    concurrently.

    Args:
        results: One IslandResult per island.
    """
    stat.track_output_variable(
        RuntimeVariable.AlgorithmIterations,
        sum(result.algorithm_iterations for result in results),
    )
    stat.track_output_variable(
        RuntimeVariable.SearchTime,
        max((result.search_time_ns for result in results), default=0),
    )


def _report_migration_stats(results: list[IslandResult]) -> None:
    """Logs each island's migration event counts and tracks the run-wide totals.

    The totals are logged and tracked as output variables. Nothing is reported
    when migration is disabled.

    Args:
        results: One IslandResult per island.
    """
    stats_by_island = [(result.island_id, result.migration_stats) for result in results]
    if all(stats is None for _island_id, stats in stats_by_island):
        return
    for island_id, stats in stats_by_island:
        _LOGGER.info("Island %d migration stats: %s", island_id, stats)
    totals = MigrationStats()
    for _island_id, stats in stats_by_island:
        if stats is None:
            continue
        totals.goal_triggered_sent += stats.goal_triggered_sent
        totals.periodic_sent += stats.periodic_sent
        totals.received += stats.received
        totals.dedup_drops += stats.dedup_drops
    _LOGGER.info("Migration stats across all islands: %s", totals)
    stat.track_output_variable(
        RuntimeVariable.MigrantsSentGoalTriggered, totals.goal_triggered_sent
    )
    stat.track_output_variable(RuntimeVariable.MigrantsSentPeriodic, totals.periodic_sent)
    stat.track_output_variable(RuntimeVariable.MigrantsReceived, totals.received)
    stat.track_output_variable(RuntimeVariable.MigrantsDroppedAsDuplicate, totals.dedup_drops)


def _receive_and_join(
    process: mp.Process, receiving_connection: mp_conn.Connection, timeout_seconds: float
) -> Any | None:
    """Waits for one message from a child process, then makes sure the process exits.

    Waiting is bounded, so a process that hangs without sending anything, e.g. in a
    native call of the SUT, is stopped instead of blocking the orchestrator forever.

    Args:
        process: The child process.
        receiving_connection: The pipe end to receive the message from.
        timeout_seconds: How long to wait for the message.

    Returns:
        The received message, or None if the process died or hung without sending one.
    """
    message: Any | None = None
    try:
        if receiving_connection.poll(timeout_seconds):
            message = receiving_connection.recv()
        else:
            _LOGGER.error(
                "Process %s sent nothing within %.0f seconds, stopping it",
                process.name,
                timeout_seconds,
            )
    except EOFError:
        _LOGGER.error("Process %s died without sending anything", process.name)
    if message is not None:
        process.join(timeout=_JOIN_TIMEOUT_SECONDS)
    if process.is_alive():
        _LOGGER.error("Process %s did not exit, terminating it", process.name)
        process.terminate()
        _join_or_kill(process)
    return message


def _collect_island_result(
    process: mp.Process, receiving_connection: mp_conn.Connection, deadline: float
) -> IslandResult | None:
    """Waits for one island's result until the deadline, then makes sure it exits.

    Args:
        process: The island's process.
        receiving_connection: The pipe end to receive its IslandResult from.
        deadline: The time.monotonic() value by which every island must have sent
            its result.

    Returns:
        The island's result, or None if it died or hung without sending one.
    """
    return _receive_and_join(process, receiving_connection, max(0.0, deadline - time.monotonic()))


def _collect_llm_worker_result(
    process: mp.Process, receiving_connection: mp_conn.Connection | None
) -> WorkerStatsReport | None:
    """Waits for the LLM worker's stats report, then makes sure its process exits.

    Args:
        process: The LLM worker's process.
        receiving_connection: The pipe end to receive its WorkerStatsReport from.

    Returns:
        The worker's stats report, or None if it died or hung without sending one.
    """
    if receiving_connection is None:
        return None
    return _receive_and_join(process, receiving_connection, _RESULT_GRACE_SECONDS)


def _track_llm_worker_stats(stats_report: WorkerStatsReport) -> None:
    """Tracks the LLM worker's aggregate stats as output variables.

    Args:
        stats_report: The worker's accumulated stats for this run.
    """
    stat.track_output_variable(RuntimeVariable.TotalLLMWorkerQueries, stats_report.queries_issued)
    stat.track_output_variable(
        RuntimeVariable.TotalLLMWorkerQueryTimeSeconds, stats_report.total_latency_seconds
    )
    stat.track_output_variable(RuntimeVariable.TotalLLMWorkerInputTokens, stats_report.input_tokens)
    stat.track_output_variable(
        RuntimeVariable.TotalLLMWorkerOutputTokens, stats_report.output_tokens
    )
    stat.track_output_variable(
        RuntimeVariable.EstimatedLLMWorkerCostUSD, stats_report.estimated_cost_usd
    )
