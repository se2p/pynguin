#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides the wire protocol between islands and the centralized LLM worker."""

from __future__ import annotations

import dataclasses
import inspect
import queue
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import multiprocess.managers as mp_managers

    import pynguin.testcase.testcase as tc
    from pynguin.utils.generic.genericaccessibleobject import (
        GenericCallableAccessibleObject,
    )


def callable_first_line(gao: GenericCallableAccessibleObject) -> int | None:
    """Return the source line where a callable starts.

    The line number is used as a simple process-safe identifier for the callable.

    Args:
        gao: The callable to inspect.

    Returns:
        The first source line of the callable, or None if it cannot be determined.
    """
    try:
        _, start_line = inspect.getsourcelines(gao.callable)
    except (TypeError, OSError):
        return None
    return start_line


@dataclasses.dataclass
class StatusReport:
    """One island's report that a callable's status changed."""

    island_id: int
    first_line: int
    coverage: float
    covered: bool


@dataclasses.dataclass
class LLMWorkerResult:
    """One completed LLM query result, addressed to the island that requested it."""

    target_island: int
    first_line: int
    test_case: tc.TestCase
    content_hash: str


@dataclasses.dataclass
class WorkerStatsReport:
    """Aggregate LLM worker statistics, sent once at worker shutdown."""

    queries_issued: int
    total_latency_seconds: float
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float


class LLMWorkerChannel:
    """One island's handle onto the LLM-worker status/result channel."""

    def __init__(
        self,
        island_id: int,
        status_queue: mp_managers.BaseProxy,
        result_inbox: mp_managers.BaseProxy,
    ) -> None:
        """Creates a channel for one island.

        Args:
            island_id: This island's own id.
            status_queue: The shared queue every island reports into; only the
                worker reads it.
            result_inbox: This island's own inbox for completed query results.
        """
        self._island_id = island_id
        self._status_queue = status_queue
        self._result_inbox = result_inbox

    def report(self, status: StatusReport) -> None:
        """Sends a status report to the worker's shared inbox.

        Args:
            status: The report to send.
        """
        self._status_queue.put(status)

    def drain_incoming(self, max_messages: int = 256) -> list[LLMWorkerResult]:
        """Non-blockingly drains up to max_messages completed results.

        Args:
            max_messages: Upper bound on how many results to drain in one call.

        Returns:
            The drained results, oldest first; empty if nothing was waiting.
        """
        drained: list[LLMWorkerResult] = []
        for _ in range(max_messages):
            result = self._try_get_nowait()
            if result is None:
                break
            drained.append(result)
        return drained

    def _try_get_nowait(self) -> LLMWorkerResult | None:
        try:
            return self._result_inbox.get_nowait()
        except queue.Empty:
            return None


def build_llm_worker_channels(
    num_islands: int, manager: mp_managers.SyncManager
) -> tuple[mp_managers.BaseProxy, dict[int, mp_managers.BaseProxy], dict[int, LLMWorkerChannel]]:
    """Create the queues and channels used by the LLM worker.

    Args:
        num_islands: Number of island channels to create.
        manager: Manager used to create the shared queues.

    Returns:
        The shared status queue, per-island result queues, and per-island channels.
    """
    status_queue = manager.Queue()
    result_inboxes = {island_id: manager.Queue() for island_id in range(num_islands)}
    channels = {
        island_id: LLMWorkerChannel(island_id, status_queue, result_inboxes[island_id])
        for island_id in range(num_islands)
    }
    return status_queue, result_inboxes, channels
