#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides the centralized asynchronous LLM query worker process."""

from __future__ import annotations

import asyncio
import dataclasses
import datetime
import logging
import pathlib
import time
import traceback
from typing import TYPE_CHECKING, cast

import multiprocess as mp

import pynguin.configuration as config
from pynguin import generator
from pynguin.generator import set_configuration
from pynguin.islands.llm_worker_protocol import (
    LLMWorkerResult,
    StatusReport,
    WorkerStatsReport,
    callable_first_line,
)
from pynguin.islands.migration import MigrationChannel, MigrationMessage, compute_test_case_hash
from pynguin.large_language_model.llmagent import LLMAgent
from pynguin.utils.generic.genericaccessibleobject import GenericCallableAccessibleObject
from pynguin.utils.logging_utils import WorkerFormatting

if TYPE_CHECKING:
    import multiprocess.connection as mp_conn
    import multiprocess.managers as mp_managers

    import pynguin.testcase.testcase as tc
    from pynguin.analyses.module import TestCluster

_LOGGER = logging.getLogger(__name__)


@dataclasses.dataclass
class LLMWorkerTask:
    """Task to be executed by the LLM worker process."""

    configuration: config.Configuration
    status_queue: mp_managers.BaseProxy
    """Shared queue for status updates from all islands."""

    result_inboxes: dict[int, mp_managers.BaseProxy]
    """Per-island queues used to deliver targeted results."""

    broadcast_inboxes: dict[int, mp_managers.BaseProxy] | None
    """Per-island migration queues used for broadcast delivery, if enabled."""


def llm_worker_main(
    task: LLMWorkerTask, sending_connection: mp_conn.Connection, test_cluster: TestCluster
) -> None:
    """Run the LLM worker process.

    The worker reuses the orchestrator's test cluster, which it inherits as a
    forked process, processes LLM requests, and sends the collected worker
    statistics back to the orchestrator.

    Args:
        task: The task assigned to the worker.
        sending_connection: Connection used to send the worker statistics.
        test_cluster: The orchestrator's test cluster; the worker works on its own
            forked copy of it.
    """
    try:
        with WorkerFormatting():
            _LOGGER.info("LLM worker process started (PID: %d)", mp.current_process().pid)
            set_configuration(task.configuration)
            generator._setup_random_number_generator()  # noqa: SLF001
            gao_by_first_line = _build_gao_by_first_line(test_cluster)
            agent = LLMAgent()
            worker = _LLMQueryWorker(task, gao_by_first_line, agent, test_cluster)
            stats_report = asyncio.run(worker.run())
            sending_connection.send(stats_report)
            _LOGGER.info("LLM worker completed %d queries", stats_report.queries_issued)
    except KeyboardInterrupt:
        _LOGGER.info("LLM worker process interrupted")
    except Exception as e:  # noqa: BLE001
        _LOGGER.error("Pynguin error in LLM worker process: %s\n%s", e, traceback.format_exc())
        try:
            sending_connection.send(WorkerStatsReport(0, 0.0, 0, 0, 0.0))
        except Exception:  # noqa: BLE001
            _LOGGER.error("Failed to send error stats report from LLM worker")


def _build_gao_by_first_line(
    test_cluster: TestCluster,
) -> dict[int, GenericCallableAccessibleObject]:
    gao_by_first_line: dict[int, GenericCallableAccessibleObject] = {}
    for gao in test_cluster.accessible_objects_under_test:
        if not isinstance(gao, GenericCallableAccessibleObject):
            continue
        first_line = callable_first_line(gao)
        if first_line is not None:
            gao_by_first_line[first_line] = gao
    return gao_by_first_line


def _append_query_log(
    report_dir: str,
    island_id: int,
    first_line: int,
    *,
    latency_seconds: float,
    input_tokens: int,
    output_tokens: int,
    coverage: float,
) -> None:
    """Append one LLM query record to the worker query log.

    The log is stored in ``llm_worker_queries.csv`` inside the report directory.
    File-system errors are logged without interrupting the worker.

    Args:
        report_dir: Directory where the query log is stored.
        island_id: ID of the island that issued the query.
        first_line: Identifier of the queried callable.
        latency_seconds: Time spent processing the query.
        input_tokens: Number of input tokens used.
        output_tokens: Number of output tokens used.
        coverage: The callable's reported goal coverage when it was selected.
    """
    try:
        output_dir = pathlib.Path(report_dir).resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / "llm_worker_queries.csv"
        is_new = not output_file.exists()
        with output_file.open(mode="a", encoding="utf-8") as file:
            if is_new:
                file.write(
                    "timestamp,island_id,first_line,latency_seconds,input_tokens,output_tokens,"
                    "coverage\n"
                )
            timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
            file.write(
                f"{timestamp},{island_id},{first_line},{latency_seconds},"
                f"{input_tokens},{output_tokens},{coverage}\n"
            )
    except OSError as error:
        _LOGGER.exception("Error while writing LLM worker query log: %s", error)


class _LLMQueryWorker:
    """Runs the priority-queue dispatch loop for one LLM worker process."""

    _logger = logging.getLogger(__name__)

    def __init__(
        self,
        task: LLMWorkerTask,
        gao_by_first_line: dict[int, GenericCallableAccessibleObject],
        agent: LLMAgent,
        test_cluster: TestCluster,
    ) -> None:
        """Creates a query worker.

        Args:
            task: This worker's task, carrying its channels and configuration.
            gao_by_first_line: Maps a callable's wire-format identifier back to
                the callable itself, for building LLM prompts.
            agent: The LLM agent to query.
            test_cluster: Passed to the test-case-handler for deserialization.
        """
        self._task = task
        self._gao_by_first_line = gao_by_first_line
        self._agent = agent
        self._test_cluster = test_cluster
        self._coverage: dict[tuple[int, int], float] = {}
        self._sem = asyncio.Semaphore(task.configuration.llm_worker.max_in_flight_requests)
        self._has_work = asyncio.Event()
        self._shutdown = asyncio.Event()
        self._inflight_tasks: set[asyncio.Task] = set()
        self._broadcast_channel = (
            MigrationChannel.for_broadcaster(task.broadcast_inboxes)
            if task.broadcast_inboxes is not None
            else None
        )
        self._queries_issued = 0
        self._total_latency_seconds = 0.0

    async def run(self) -> WorkerStatsReport:
        """Runs the status-listener and dispatch loops until shutdown.

        The shutdown sentinel marks the end of island search, so no island can use
        a result any more. Pending targets are dropped instead of queried, and
        in-flight requests are cancelled.

        Returns:
            The accumulated stats for this worker's whole run.
        """
        listener = asyncio.create_task(self._status_report_listener())
        dispatcher = asyncio.create_task(self._dispatch_loop())
        await self._shutdown.wait()
        dropped_targets = len(self._coverage)
        self._coverage.clear()
        self._has_work.clear()
        listener.cancel()
        dispatcher.cancel()
        await asyncio.gather(listener, dispatcher, return_exceptions=True)
        self._logger.info(
            "LLM worker shutting down: dropped %d pending target(s), cancelling %d "
            "in-flight request(s)",
            dropped_targets,
            len(self._inflight_tasks),
        )
        # Cancel in-flight requests so they fail immediately instead of waiting for
        # their configured timeout. This keeps shutdown bounded and matches the
        # search algorithms' shutdown behavior.
        if hasattr(self._agent, "cancel_all"):
            self._agent.cancel_all()
        for inflight_task in self._inflight_tasks:
            inflight_task.cancel()
        if self._inflight_tasks:
            await asyncio.wait(self._inflight_tasks, timeout=5)
        return WorkerStatsReport(
            queries_issued=self._queries_issued,
            total_latency_seconds=self._total_latency_seconds,
            input_tokens=self._agent.llm_input_tokens,
            output_tokens=self._agent.llm_output_tokens,
            estimated_cost_usd=self._estimate_cost(),
        )

    def _estimate_cost(self) -> float:
        llm_worker_config = self._task.configuration.llm_worker
        return (
            self._agent.llm_input_tokens / 1000 * llm_worker_config.cost_per_1k_input_tokens
            + self._agent.llm_output_tokens / 1000 * llm_worker_config.cost_per_1k_output_tokens
        )

    async def _status_report_listener(self) -> None:
        loop = asyncio.get_running_loop()
        while True:
            report = await loop.run_in_executor(None, self._task.status_queue.get)
            if report is None:
                self._shutdown.set()
                return
            self._update_coverage(cast("StatusReport", report))

    def _update_coverage(self, report: StatusReport) -> None:
        self._logger.debug(
            "LLM worker status report: island %d, callable at line %d, coverage %r%s",
            report.island_id,
            report.first_line,
            report.coverage,
            " (covered)" if report.covered else "",
        )
        key = (report.island_id, report.first_line)
        if report.covered:
            self._coverage.pop(key, None)
        else:
            self._coverage[key] = report.coverage
        if self._coverage:
            self._has_work.set()

    def _pop_lowest_coverage(self) -> tuple[tuple[int, int], float] | None:
        """Pops the (island, callable) pair with the highest priority (1-coverage).

        Items with the same coverage are returned in insertion order.

        Returns:
            The popped (key, coverage), or None if nothing is pending.
        """
        if not self._coverage:
            self._has_work.clear()
            return None
        key = min(self._coverage, key=self._coverage.get)  # type: ignore[arg-type]
        coverage = self._coverage.pop(key)
        self._logger.info(
            "LLM worker queries island %d, callable at line %d (coverage %r, %d pending)",
            key[0],
            key[1],
            coverage,
            len(self._coverage),
        )
        if not self._coverage:
            self._has_work.clear()
        return key, coverage

    async def _dispatch_loop(self) -> None:
        while True:
            await self._has_work.wait()
            await self._sem.acquire()
            popped = self._pop_lowest_coverage()
            if popped is None:
                self._sem.release()
                continue
            key, coverage = popped
            handler_task = asyncio.create_task(self._handle_one_query(key, coverage))
            self._inflight_tasks.add(handler_task)
            handler_task.add_done_callback(self._inflight_tasks.discard)

    async def _handle_one_query(self, key: tuple[int, int], coverage: float) -> None:
        """Queries the LLM for one (island, callable) pair and delivers the result.

        Uses the shared asynchronous query path so existing retry, caching, and
        cancellation behavior is preserved.

        Args:
            key: The (island_id, first_line) pair identifying the request.
            coverage: The target's current coverage, for the prompt.
        """
        island_id, first_line = key
        try:
            gao = self._gao_by_first_line.get(first_line)
            if gao is None:
                return
            input_tokens_before = self._agent.llm_input_tokens
            output_tokens_before = self._agent.llm_output_tokens
            start = time.time()
            raw_result = await self._agent.call_llm_for_uncovered_targets_async(
                {gao: coverage}, None
            )
            latency_seconds = time.time() - start
            self._total_latency_seconds += latency_seconds
            self._queries_issued += 1
            # LLMAgent only exposes cumulative totals, not a per-call breakdown, so
            # this delta is exact only when requests don't overlap
            # (max_in_flight_requests=1, the default); under real concurrent
            # dispatch it's a best-effort approximation, not an exact attribution.
            query_input_tokens = self._agent.llm_input_tokens - input_tokens_before
            query_output_tokens = self._agent.llm_output_tokens - output_tokens_before
            _append_query_log(
                self._task.configuration.statistics_output.report_dir,
                island_id,
                first_line,
                latency_seconds=latency_seconds,
                input_tokens=query_input_tokens,
                output_tokens=query_output_tokens,
                coverage=coverage,
            )
            loop = asyncio.get_running_loop()
            test_cases = await loop.run_in_executor(
                None,
                self._agent.llm_test_case_handler.get_test_cases_from_llm_results,
                raw_result,
                self._test_cluster,
            )
            for test_case in test_cases:
                self._deliver(island_id, first_line, test_case)
            broadcasting = (
                self._task.configuration.llm_worker.immigration_routing
                is config.ImmigrationRouting.BROADCAST
                and self._broadcast_channel is not None
            )
            self._logger.info(
                "LLM worker delivered %d test case(s) for callable at line %d to %s",
                len(test_cases),
                first_line,
                "all islands" if broadcasting else f"island {island_id}",
            )
        finally:
            self._sem.release()

    def _deliver(self, target_island: int, first_line: int, test_case: tc.TestCase) -> None:
        content_hash = compute_test_case_hash(test_case)
        routing = self._task.configuration.llm_worker.immigration_routing
        if routing is config.ImmigrationRouting.TARGETED or self._broadcast_channel is None:
            self._task.result_inboxes[target_island].put(
                LLMWorkerResult(
                    target_island=target_island,
                    first_line=first_line,
                    test_case=test_case,
                    content_hash=content_hash,
                )
            )
        else:
            self._broadcast_channel.broadcast(
                MigrationMessage(
                    source_island=-1,
                    covered_goal=None,
                    content_hash=content_hash,
                    test_case=test_case,
                )
            )
