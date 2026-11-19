#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides the entry point run by each island process."""

from __future__ import annotations

import contextlib
import dataclasses
import gc
import logging
import os
import signal
import threading
import traceback
from pathlib import Path
from typing import TYPE_CHECKING, cast

import multiprocess as mp
import multiprocess.connection as mp_conn

import pynguin.ga.generationalgorithmfactory as gaf
import pynguin.utils.statistics.stats as stat
from pynguin import generator
from pynguin.ga.algorithms.dynamosaalgorithm import DynaMOSAAlgorithm
from pynguin.ga.stoppingcondition import MaxMemoryStoppingCondition
from pynguin.generator import ReturnCode, set_configuration
from pynguin.islands.llm_worker_algorithm import IslandLLMWorkerExtension
from pynguin.islands.migration import portable_execution_result, portable_test_case
from pynguin.islands.migration_algorithm import IslandMigrationExtension
from pynguin.utils.exceptions import ConfigurationException, TracingAbortedException
from pynguin.utils.logging_utils import WorkerFormatting
from pynguin.utils.statistics.runtimevariable import RuntimeVariable

if TYPE_CHECKING:
    from collections.abc import Iterator

    import pynguin.configuration as config
    import pynguin.ga.coveragegoals as bg
    import pynguin.ga.testcasechromosome as tcc
    import pynguin.ga.testsuitechromosome as tsc
    import pynguin.testcase.testcase as tc
    from pynguin.analyses.constants import ConstantProvider
    from pynguin.analyses.module import ModuleTestCluster
    from pynguin.ga.algorithms.generationalgorithm import GenerationAlgorithm
    from pynguin.islands.llm_worker_protocol import LLMWorkerChannel
    from pynguin.islands.migration import MigrationChannel
    from pynguin.islands.migration_algorithm import MigrationStats
    from pynguin.testcase.execution import TestCaseExecutor
    from pynguin.testcase.execution_result import ExecutionResult


_LOGGER = logging.getLogger(__name__)

# Random integers in generated tests lie within +-max_int and drift beyond it only
# slowly through mutation. The island's own connections get file descriptors above
# this multiple of max_int.
_CONNECTION_FD_FLOOR_FACTOR = 4

# The number of file descriptors above the floor that no integer constant of the
# SUT may take, so that the island's own connections can use them.
_CONNECTION_FD_WINDOW = 16

# File descriptors the island may open above the floor for its own connections.
_CONNECTION_FD_HEADROOM = 1024

# The island's data size is limited to this multiple of maximum_memory. The search
# stops once its memory use exceeds maximum_memory, which it checks only after each
# generation, so a search that grows steadily must reach that check well before the
# limit: close to the limit, Python cannot even raise a MemoryError and aborts.
_DATA_SIZE_LIMIT_FACTOR = 2

# Seconds an island's search may run beyond maximum_search_time before the island
# interrupts it, well before the orchestrator stops waiting for its result.
_SEARCH_OVERRUN_GRACE_SECONDS = 60

# Seconds between two interrupts of an island's search that overran its time.
_SEARCH_INTERRUPT_INTERVAL_SECONDS = 1

# Where Linux describes which physical core each CPU (hardware thread) belongs to.
_CPU_TOPOLOGY_ROOT = Path("/sys/devices/system/cpu")

# The message of the RuntimeError raised when no thread can be started, e.g., because
# the stacks of test-execution threads that could not be stopped used up the data size.
_CANNOT_START_THREAD = "can't start new thread"


class _SearchOverrunError(Exception):
    """Raised in an island's main thread when its search overran its time."""


@dataclasses.dataclass
class IslandTask:
    """Task to be executed by an island process."""

    island_id: int
    configuration: config.Configuration
    """The orchestrator must set a unique seed and island ID
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

    coverage_timeline: list[tuple[int, float]] = dataclasses.field(default_factory=list)
    """The island's CoverageTimeline samples as ``(time_stamp_ns, coverage)``, with
    time stamps in nanoseconds since the island's search start. The orchestrator
    merges them into its own CoverageTimeline output variable.
    """

    migration_stats: MigrationStats | None = None
    """Migration statistics recorded when migration is enabled.
    Includes sent, received, and duplicate-drop counts used by the orchestrator
    for migration logging.
    """

    algorithm_iterations: int = 0
    """The number of generations the island's search ran (AlgorithmIterations)."""

    search_time_ns: int = 0
    """The wall-clock time of the island's search in nanoseconds (SearchTime)."""

    execution_results: list[ExecutionResult | None] = dataclasses.field(default_factory=list)
    """The execution result the search recorded for each of the test cases, at the
    same position, or None where none can be sent. Empty if none were sent.
    """

    line_coverage_timeline: list[tuple[int, float]] = dataclasses.field(default_factory=list)
    """The island's LineCoverageTimeline samples, like coverage_timeline; empty unless
    LineCoverageTimeline is an output variable.
    """


@contextlib.contextmanager
def _new_fds_from(floor: int) -> Iterator[bool]:
    """Make the file descriptors opened inside the context get numbers >= floor.

    Every free number below floor is taken by a placeholder until the context
    exits. The open-file limit is raised for this if needed.

    Args:
        floor: The smallest file descriptor number to hand out inside the context.

    Yields:
        Whether new file descriptors get numbers >= floor; False if the open-file
        limit cannot be raised far enough.
    """
    # POSIX only, like the fork start method island mode requires.
    import resource  # noqa: PLC0415

    soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    needed = floor + _CONNECTION_FD_HEADROOM
    if soft < needed:
        try:
            resource.setrlimit(resource.RLIMIT_NOFILE, (needed, hard))
        except (ValueError, OSError):
            yield False
            return
    placeholders: list[int] = []
    try:
        while not placeholders or placeholders[-1] < floor - 1:
            placeholders.append(os.open(os.devnull, os.O_RDONLY))
        yield True
    finally:
        for placeholder in placeholders:
            os.close(placeholder)


@contextlib.contextmanager
def _limited_data_size(task: IslandTask) -> Iterator[None]:
    """Make an allocation beyond the island's memory budget fail during its search.

    The islands share the memory of the job. A SUT call that allocates a huge
    string or buffer runs in native code, which a test-execution timeout cannot
    stop, and the operating system hands out such memory lazily, so the call keeps
    growing until the job's memory limit kills one of the processes. The island's
    data size is therefore limited to a multiple of maximum_memory, the memory after
    which a search stops anyway. Such an allocation in a test raises a MemoryError,
    which the test records like any other exception; one in the search ends it.
    The previous limit applies again afterwards, when the island builds its result.

    Args:
        task: The island task whose configuration holds maximum_memory.

    Yields:
        Nothing; the limit applies inside the context.
    """
    maximum_memory = task.configuration.stopping.maximum_memory
    if maximum_memory < 0:
        yield
        return
    # POSIX only, like the fork start method island mode requires.
    import resource  # noqa: PLC0415

    soft, hard = resource.getrlimit(resource.RLIMIT_DATA)
    limit = _DATA_SIZE_LIMIT_FACTOR * maximum_memory * MaxMemoryStoppingCondition.MB_TO_BYTES
    if hard != resource.RLIM_INFINITY:
        limit = min(limit, hard)
    try:
        resource.setrlimit(resource.RLIMIT_DATA, (limit, hard))
    except (ValueError, OSError):
        limited = False
    else:
        limited = True
    if not limited:
        _LOGGER.warning(
            "Island %d cannot limit its data size to %d MB",
            task.island_id,
            limit // MaxMemoryStoppingCondition.MB_TO_BYTES,
        )
        yield
        return
    try:
        yield
    finally:
        resource.setrlimit(resource.RLIMIT_DATA, (soft, hard))


@contextlib.contextmanager
def _interrupting_overrun(search_time: float) -> Iterator[None]:
    """Interrupt the island's search once it overran its search time.

    A test-execution thread that is stopped while holding a lock of the SUT, e.g.,
    tqdm's write lock, leaves the lock held. The garbage collector runs the SUT's
    finalizers in whichever thread allocates, so the island's main thread can wait
    forever for that lock in a finalizer and never send its result. Once the search
    overran its time by a grace period, the main thread is therefore interrupted
    every second by a signal whose handler raises a _SearchOverrunError. Python
    ignores an exception raised in a finalizer, so the search goes on and ends at
    its next check of the search time; elsewhere the exception ends the search.

    Args:
        search_time: The search time in seconds, negative for none.

    Yields:
        Nothing; the search runs inside the context.
    """
    if search_time < 0:
        yield
        return
    searching = True
    interrupted = False
    done = threading.Event()
    main_thread_id = threading.get_ident()

    def raise_overrun(_signal_number: int, _frame: object) -> None:
        if searching:
            raise _SearchOverrunError

    def interrupt_when_overrun() -> None:
        nonlocal interrupted
        if done.wait(search_time + _SEARCH_OVERRUN_GRACE_SECONDS):
            return
        while True:
            interrupted = True
            signal.pthread_kill(main_thread_id, signal.SIGUSR1)
            if done.wait(_SEARCH_INTERRUPT_INTERVAL_SECONDS):
                return

    previous_handler = signal.signal(signal.SIGUSR1, raise_overrun)
    watchdog = threading.Thread(target=interrupt_when_overrun, daemon=True)
    watchdog.start()
    try:
        yield
    finally:
        searching = False
        done.set()
        watchdog.join()
        # A signal sent just before can still arrive; the handler then does nothing.
        if not interrupted:
            signal.signal(signal.SIGUSR1, previous_handler)


def _search(task: IslandTask, algorithm: GenerationAlgorithm) -> tsc.TestSuiteChromosome:
    """Run the island's search within its memory budget and time.

    A search that runs out of the island's memory, which includes being unable to
    start a test-execution thread, or overran its time ends early with the archive
    it has, so the island still sends what it found. The SUT can replace the logging
    handlers with its own instrumented code, which aborts in this thread while a
    stopped test-execution thread is still traced, so a failing warning is ignored.

    Args:
        task: The island task whose configuration holds the memory budget and time.
        algorithm: The island's search algorithm.

    Returns:
        The test suite of the search.
    """
    try:
        with (
            _limited_data_size(task),
            _interrupting_overrun(task.configuration.stopping.maximum_search_time),
        ):
            return algorithm.generate_tests()
    except (MemoryError, RuntimeError, _SearchOverrunError) as error:
        if isinstance(error, RuntimeError) and str(error) != _CANNOT_START_THREAD:
            raise
        with contextlib.suppress(TracingAbortedException):
            _LOGGER.warning(
                "Island %d ends its search early after %s", task.island_id, type(error).__name__
            )
        algorithm.after_search_finish()
        return algorithm.create_test_suite(algorithm.archive.solutions)


def _portable_last_execution_result(
    chromosome: tcc.TestCaseChromosome,
) -> ExecutionResult | None:
    """Return the sendable execution result the search recorded for a test case.

    Args:
        chromosome: A test case of the search's final archive.

    Returns:
        The sendable result, or None if the test case changed since it was last
        executed or its result cannot be sent.
    """
    result = chromosome.get_last_execution_result()
    if chromosome.changed or result is None:
        return None
    return portable_execution_result(result)


def _connection_fd_floor(max_int: int, constant_provider: ConstantProvider) -> int:
    """Find file descriptor numbers that no integer in a generated test takes.

    Generated tests contain random integers within +-max_int and the integer
    constants the constant provider knows. The floor starts above the former and
    moves past every constant that would fall into the window of file
    descriptors above it.

    Args:
        max_int: The largest magnitude of a random integer in a generated test.
        constant_provider: The provider of the constants used in generated tests.

    Returns:
        The floor of the window of file descriptors for the island's connections.
    """
    floor = _CONNECTION_FD_FLOOR_FACTOR * max_int
    for constant in sorted(c for c in constant_provider.get_all_constants_for(int) if c >= floor):
        if constant >= floor + _CONNECTION_FD_WINDOW:
            break
        floor = constant + 1
    return floor


def _first_cpu_per_core(topology_root: Path = _CPU_TOPOLOGY_ROOT) -> list[int] | None:
    """List one CPU of each physical core this process may run on.

    Args:
        topology_root: Where Linux describes the CPU topology.

    Returns:
        The first allowed hardware thread of each physical core, in CPU order, or
        None if the allowed CPUs or their cores cannot be determined.
    """
    if not hasattr(os, "sched_getaffinity"):
        return None
    first_cpus: dict[tuple[str, str], int] = {}
    try:
        for cpu in sorted(os.sched_getaffinity(0)):
            topology = topology_root / f"cpu{cpu}" / "topology"
            core = (
                (topology / "physical_package_id").read_text().strip(),
                (topology / "core_id").read_text().strip(),
            )
            first_cpus.setdefault(core, cpu)
    except OSError:
        return None
    return list(first_cpus.values())


def _pin_to_own_core(task: IslandTask) -> None:
    """Run the island on a physical core of its own.

    A job gets whole cores, each with two hardware threads, one core per island.
    The operating system still often runs two islands on the two threads of one
    core while another core stays idle, and each of them then gets only part of the
    core's speed. Each island therefore binds itself, and the test-execution threads
    it starts, to its own core, if the process may run on a core per island.

    Args:
        task: The island task with the island's id and the number of islands.
    """
    cpus = _first_cpu_per_core()
    if (
        not hasattr(os, "sched_setaffinity")
        or cpus is None
        or len(cpus) < task.configuration.island.num_islands
    ):
        return
    os.sched_setaffinity(0, {cpus[task.island_id]})
    _LOGGER.info("Island %d runs on CPU %d", task.island_id, cpus[task.island_id])


def _move_connections_beyond_sut_reach(
    task: IslandTask,
    sending_connection: mp_conn.Connection,
    constant_provider: ConstantProvider,
) -> mp_conn.Connection:
    """Give the island's own connections file descriptors the SUT cannot reach.

    The SUT code an island executes can read from, write to, or close any file
    descriptor it gets as an integer, e.g., when it opens an int as a file name.
    A test-execution thread that cannot be stopped can even keep reading one and
    consume the Manager's replies, so the island waits for them forever. The
    island's result pipe and its Manager connections therefore get file
    descriptors that no integer in a generated test takes.

    Args:
        task: The island task with the channels whose connections to open.
        sending_connection: The island's end of its result pipe.
        constant_provider: The provider of the constants used in generated tests.

    Returns:
        The island's end of its result pipe to send the result through.
    """
    floor = _connection_fd_floor(task.configuration.test_creation.max_int, constant_provider)
    with _new_fds_from(floor) as beyond_reach:
        if not beyond_reach:
            _LOGGER.warning(
                "Island %d cannot raise its open-file limit above %d; the SUT can "
                "reach its connections",
                task.island_id,
                floor,
            )
            return sending_connection
        moved_connection = mp_conn.Connection(os.dup(sending_connection.fileno()), readable=False)
        if task.migration_channel is not None:
            task.migration_channel.open_connections()
        if task.llm_worker_channel is not None:
            task.llm_worker_channel.open_connections()
    sending_connection.close()
    return moved_connection


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
    migrants just unlocked. Only islands with such a channel must run DynaMOSA;
    without one, any algorithm is returned unchanged. Runs without islands never
    reach this function.

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
    setup_result: tuple[TestCaseExecutor, ModuleTestCluster, ConstantProvider],
) -> None:
    """Run test generation for a single island.

    The island reuses the orchestrator's SUT setup, which it inherits as a forked
    process, and only reseeds the random number generators with its own seed. It
    then searches and sends the generated test cases and related search data back
    to the orchestrator. Final assertion generation and export are handled after
    the island results are merged.

    Args:
        task: The task assigned to the island.
        sending_connection: Connection used to send the result to the orchestrator.
        setup_result: The orchestrator's executor, test cluster, and constant
            provider; the island works on its own forked copy of them.
    """
    try:
        with WorkerFormatting():
            _LOGGER.info(
                "Island %d process started (PID: %d)", task.island_id, mp.current_process().pid
            )
            set_configuration(task.configuration)
            _pin_to_own_core(task)
            _LOGGER.info(
                "Island %d population size %d",
                task.island_id,
                task.configuration.search_algorithm.population,
            )
            generator._setup_random_number_generator()  # noqa: SLF001
            executor, test_cluster, constant_provider = setup_result
            sending_connection = _move_connections_beyond_sut_reach(
                task, sending_connection, constant_provider
            )
            algorithm, migration_extension = _build_algorithm(
                task, executor, test_cluster, constant_provider
            )
            generation_result = _search(task, algorithm)
            # The garbage collector would run SUT finalizers, which can wait forever
            # for a lock a stopped test-execution thread left held; the island exits
            # right after sending its result.
            gc.disable()
            sent = [
                (portable, _portable_last_execution_result(chromosome))
                for chromosome in generation_result.test_case_chromosomes
                if (portable := portable_test_case(chromosome.test_case)) is not None
            ]
            test_cases = [test_case for test_case, _ in sent]
            covered_goals = [
                cast("bg.BranchGoal", cast("bg.BranchCoverageTestFitness", target).goal)
                for target in algorithm.archive.covered_goals
            ]
            migration_stats = migration_extension.stats if migration_extension is not None else None
            tracked = dict(stat.statistics_tracker.variables_generator)
            sending_connection.send(
                IslandResult(
                    task.island_id,
                    test_cases,
                    ReturnCode.OK,
                    covered_goals,
                    stat.get_sequence_samples(RuntimeVariable.CoverageTimeline),
                    migration_stats,
                    algorithm_iterations=tracked.get(RuntimeVariable.AlgorithmIterations, 0),
                    search_time_ns=tracked.get(RuntimeVariable.SearchTime, 0),
                    execution_results=[result for _, result in sent],
                    line_coverage_timeline=(
                        stat.get_sequence_samples(RuntimeVariable.LineCoverageTimeline)
                        if stat.tracks_sequence(RuntimeVariable.LineCoverageTimeline)
                        else []
                    ),
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
