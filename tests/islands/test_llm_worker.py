#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Tests for the centralized asynchronous LLM query worker."""

import asyncio
import csv
import dataclasses
import logging
import queue
import threading
import time
from unittest.mock import MagicMock

import multiprocess as mp

import pynguin.configuration as config
from pynguin import generator
from pynguin.islands import llm_worker
from pynguin.islands.llm_worker import LLMWorkerTask, llm_worker_main
from pynguin.islands.llm_worker_protocol import StatusReport


@dataclasses.dataclass
class _FakeTestCase:
    """A plain, hashable stand-in for TestCase.

    MagicMock's to_code() isn't a real string, which compute_test_case_hash() needs.
    """

    source: str

    def to_code(self) -> str:
        return self.source


class _StubTestCaseHandler:
    def get_test_cases_from_llm_results(self, raw_result, test_cluster):
        return []


class _StubAgent:
    def __init__(self):
        self.llm_input_tokens = 0
        self.llm_output_tokens = 0
        self.llm_test_case_handler = _StubTestCaseHandler()
        self.calls = []
        self.concurrent = 0
        self.max_concurrent_seen = 0
        self._lock = threading.Lock()

    async def call_llm_for_uncovered_targets_async(self, gao_coverage_map, diagnostics):
        with self._lock:
            self.concurrent += 1
            self.max_concurrent_seen = max(self.max_concurrent_seen, self.concurrent)
        await asyncio.sleep(0.05)
        self.calls.append(dict(gao_coverage_map))
        self.llm_input_tokens += 10
        self.llm_output_tokens += 20
        with self._lock:
            self.concurrent -= 1
        return "raw"


def _build_configuration(tmp_path, max_in_flight, routing):
    return config.Configuration(
        algorithm=config.Algorithm.LLDYNAMOSA,
        module_name="example",
        project_path=".",
        test_case_output=config.TestCaseOutputConfiguration(output_path=str(tmp_path)),
        llm_worker=config.LLMWorkerConfiguration(
            enabled=True, max_in_flight_requests=max_in_flight, immigration_routing=routing
        ),
    )


def _build_worker(
    tmp_path,
    max_in_flight=1,
    routing=config.ImmigrationRouting.TARGETED,
    num_islands=2,
):
    configuration = _build_configuration(tmp_path, max_in_flight, routing)
    status_queue: queue.Queue = queue.Queue()
    result_inboxes: dict[int, queue.Queue] = {
        island_id: queue.Queue() for island_id in range(num_islands)
    }
    task = LLMWorkerTask(
        configuration=configuration,
        status_queue=status_queue,
        result_inboxes=result_inboxes,
        broadcast_inboxes=None,
    )
    gao_by_first_line = {10: MagicMock(), 20: MagicMock()}
    agent = _StubAgent()
    worker = llm_worker._LLMQueryWorker(
        task,
        gao_by_first_line,  # type: ignore[arg-type]
        agent,  # type: ignore[arg-type]
        MagicMock(),
    )
    return worker, status_queue, result_inboxes, agent


def test_pop_lowest_coverage_returns_lowest_coverage_first(tmp_path):
    worker, *_ = _build_worker(tmp_path)
    worker._update_coverage(StatusReport(island_id=0, first_line=10, coverage=0.8, covered=False))
    worker._update_coverage(StatusReport(island_id=0, first_line=20, coverage=0.2, covered=False))

    key, coverage = worker._pop_lowest_coverage()

    assert key == (0, 20)
    assert coverage == 0.2


def test_pop_lowest_coverage_fifo_tie_break_for_equal_coverage(tmp_path):
    worker, *_ = _build_worker(tmp_path)
    worker._update_coverage(StatusReport(island_id=0, first_line=10, coverage=0.5, covered=False))
    worker._update_coverage(StatusReport(island_id=1, first_line=20, coverage=0.5, covered=False))

    key, _coverage = worker._pop_lowest_coverage()

    assert key == (0, 10)


def test_update_coverage_removes_entry_when_covered(tmp_path):
    worker, *_ = _build_worker(tmp_path)
    worker._update_coverage(StatusReport(island_id=0, first_line=10, coverage=0.9, covered=False))
    worker._update_coverage(StatusReport(island_id=0, first_line=10, coverage=1.0, covered=True))

    assert worker._pop_lowest_coverage() is None


def test_pop_lowest_coverage_returns_none_when_empty(tmp_path):
    worker, *_ = _build_worker(tmp_path)
    assert worker._pop_lowest_coverage() is None


def test_dispatch_loop_never_exceeds_max_in_flight_requests(tmp_path):
    worker, _status_queue, _result_inboxes, agent = _build_worker(
        tmp_path, max_in_flight=2, num_islands=3
    )
    for island_id, first_line, coverage in [(0, 10, 0.9), (1, 20, 0.8), (2, 10, 0.7)]:
        worker._update_coverage(
            StatusReport(
                island_id=island_id, first_line=first_line, coverage=coverage, covered=False
            )
        )

    async def _drive():
        dispatcher = asyncio.create_task(worker._dispatch_loop())
        await asyncio.sleep(0.3)
        dispatcher.cancel()
        await asyncio.gather(dispatcher, return_exceptions=True)
        if worker._inflight_tasks:
            await asyncio.wait(worker._inflight_tasks, timeout=1)

    asyncio.run(_drive())

    assert len(agent.calls) == 3
    assert agent.max_concurrent_seen <= 2


def test_targeted_routing_delivers_only_to_the_addressed_island(tmp_path):
    worker, _status_queue, result_inboxes, _agent = _build_worker(
        tmp_path, routing=config.ImmigrationRouting.TARGETED, num_islands=2
    )
    worker._deliver(
        target_island=1,
        first_line=10,
        test_case=_FakeTestCase("def test_0():\n    pass\n"),
    )

    assert result_inboxes[1].qsize() == 1
    assert result_inboxes[0].qsize() == 0


def test_broadcast_routing_delivers_via_broadcast_channel_to_every_island(tmp_path):
    """Global Broadcast Migration always goes through the broadcast channel.

    It is never rewired onto a single destination the way periodic migration's
    one-neighbor send works, regardless of the islands' migration strategy.
    """
    configuration = _build_configuration(
        tmp_path, max_in_flight=1, routing=config.ImmigrationRouting.BROADCAST
    )
    status_queue: queue.Queue = queue.Queue()
    result_inboxes: dict[int, queue.Queue] = {0: queue.Queue(), 1: queue.Queue(), 2: queue.Queue()}
    broadcast_inboxes: dict[int, queue.Queue] = {
        0: queue.Queue(),
        1: queue.Queue(),
        2: queue.Queue(),
    }
    task = LLMWorkerTask(
        configuration=configuration,
        status_queue=status_queue,
        result_inboxes=result_inboxes,
        broadcast_inboxes=broadcast_inboxes,
    )
    worker = llm_worker._LLMQueryWorker(
        task,
        {10: MagicMock()},  # type: ignore[arg-type]
        _StubAgent(),  # type: ignore[arg-type]
        MagicMock(),
    )

    worker._deliver(
        target_island=1,
        first_line=10,
        test_case=_FakeTestCase("def test_0():\n    pass\n"),
    )

    assert broadcast_inboxes[0].qsize() == 1
    assert broadcast_inboxes[1].qsize() == 1
    assert broadcast_inboxes[2].qsize() == 1
    assert result_inboxes[0].qsize() == 0
    assert result_inboxes[1].qsize() == 0
    assert result_inboxes[2].qsize() == 0


def test_run_processes_reports_and_returns_stats(tmp_path):
    worker, status_queue, _result_inboxes, agent = _build_worker(tmp_path, max_in_flight=1)

    async def _drive():
        run = asyncio.create_task(worker.run())
        status_queue.put(StatusReport(island_id=0, first_line=10, coverage=0.5, covered=False))
        await asyncio.sleep(0.3)
        status_queue.put(None)
        return await run

    stats = asyncio.run(_drive())

    assert stats.queries_issued == 1
    assert stats.input_tokens == 10
    assert stats.output_tokens == 20
    assert len(agent.calls) == 1


def test_run_drops_pending_targets_on_shutdown(tmp_path):
    worker, status_queue, _result_inboxes, agent = _build_worker(
        tmp_path, max_in_flight=1, num_islands=3
    )
    for island_id in range(3):
        worker._update_coverage(
            StatusReport(island_id=island_id, first_line=10, coverage=0.5, covered=False)
        )
    status_queue.put(None)

    stats = asyncio.run(worker.run())

    assert worker._coverage == {}
    assert len(agent.calls) <= 1
    assert stats.queries_issued <= 1


class _SlowStubAgent(_StubAgent):
    async def call_llm_for_uncovered_targets_async(self, gao_coverage_map, diagnostics):
        await asyncio.sleep(30)
        return await super().call_llm_for_uncovered_targets_async(gao_coverage_map, diagnostics)


def test_run_cancels_in_flight_requests_on_shutdown(tmp_path):
    worker, status_queue, _result_inboxes, _agent = _build_worker(tmp_path, max_in_flight=1)
    worker._agent = _SlowStubAgent()

    async def _drive():
        run = asyncio.create_task(worker.run())
        status_queue.put(StatusReport(island_id=0, first_line=10, coverage=0.5, covered=False))
        await asyncio.sleep(0.3)
        status_queue.put(None)
        return await run

    started = time.monotonic()
    stats = asyncio.run(_drive())

    assert time.monotonic() - started < 5
    assert stats.queries_issued == 0
    assert worker._inflight_tasks == set()


def test_run_calls_cancel_all_on_shutdown(tmp_path):
    worker, status_queue, _result_inboxes, agent = _build_worker(tmp_path, max_in_flight=1)
    agent.cancel_all = MagicMock()

    async def _drive():
        status_queue.put(None)
        return await worker.run()

    asyncio.run(_drive())

    agent.cancel_all.assert_called_once()


def test_llm_worker_main_sends_stats_report_via_real_process(tmp_path):
    configuration = _build_configuration(
        tmp_path, max_in_flight=1, routing=config.ImmigrationRouting.TARGETED
    )
    configuration.project_path = "docs/source/_static"
    configuration.llm_worker.enabled = True
    generator.set_configuration(configuration)
    _executor, test_cluster, _constant_provider = generator._setup_and_check()

    with mp.Manager() as manager:
        status_queue = manager.Queue()
        result_inboxes = {0: manager.Queue()}
        task = LLMWorkerTask(
            configuration=configuration,
            status_queue=status_queue,
            result_inboxes=result_inboxes,
            broadcast_inboxes=None,
        )
        receiving_connection, sending_connection = mp.Pipe(duplex=False)
        status_queue.put(None)
        process = mp.get_context("fork").Process(
            target=llm_worker_main, args=(task, sending_connection, test_cluster)
        )
        process.start()
        sending_connection.close()
        stats_report = receiving_connection.recv()
        process.join(timeout=10)

    assert process.exitcode == 0
    assert stats_report.queries_issued == 0


def test_pop_lowest_coverage_logs_the_selected_island_callable_and_coverage(tmp_path, caplog):
    worker, *_ = _build_worker(tmp_path)
    worker._update_coverage(StatusReport(island_id=1, first_line=20, coverage=0.25, covered=False))
    worker._update_coverage(StatusReport(island_id=0, first_line=10, coverage=0.75, covered=False))

    with caplog.at_level(logging.INFO, logger=llm_worker.__name__):
        worker._pop_lowest_coverage()

    assert "LLM worker queries island 1, callable at line 20 (coverage 0.25, 1 pending)" in (
        caplog.text
    )


def test_query_log_records_the_selected_coverage_and_the_delivery(tmp_path, caplog):
    worker, status_queue, _result_inboxes, _agent = _build_worker(tmp_path, max_in_flight=1)
    worker._task.configuration.statistics_output.report_dir = str(tmp_path)

    async def _drive():
        run = asyncio.create_task(worker.run())
        status_queue.put(StatusReport(island_id=0, first_line=10, coverage=0.5, covered=False))
        await asyncio.sleep(0.3)
        status_queue.put(None)
        return await run

    with caplog.at_level(logging.INFO, logger=llm_worker.__name__):
        asyncio.run(_drive())

    rows = list(csv.DictReader((tmp_path / "llm_worker_queries.csv").open()))
    assert len(rows) == 1
    assert rows[0]["island_id"] == "0"
    assert rows[0]["first_line"] == "10"
    assert float(rows[0]["coverage"]) == 0.5
    assert "LLM worker delivered 0 test case(s) for callable at line 10 to island 0" in (
        caplog.text
    )
