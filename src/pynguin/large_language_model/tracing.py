# This file is part of Pynguin.
#
# SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
# SPDX-License-Identifier: MIT
#
"""Structured traces and outcome statistics for individual LLM calls.

Every logical LLM call (one prompt, including the retries the client performs
for it) is described by an :class:`LLMCallRecord`.  When
``large_language_model.trace_dir`` is set, each record is appended as one JSON
line to ``llm_calls.jsonl`` in that directory.
"""

from __future__ import annotations

import dataclasses
import datetime
import enum
import json
import logging
import threading
import uuid
from pathlib import Path
from typing import Any

import pynguin.configuration as config
import pynguin.utils.statistics.stats as stat
from pynguin.utils.statistics.runtimevariable import RuntimeVariable

_logger = logging.getLogger(__name__)

TRACE_FILE_NAME = "llm_calls.jsonl"

# Serialises trace writes and the read-modify-write of the outcome counters, which
# several threads (search thread, background LLM worker) may update concurrently.
_LOCK = threading.Lock()


class CallPurpose(str, enum.Enum):
    """Why an LLM call was made."""

    INITIAL = "initial"
    """Pre-search generation of tests for the whole module."""

    UNCOVERED_TARGETS = "uncovered-targets"
    """Pre-search query for the targets the initial population leaves uncovered."""

    STALL = "stall"
    """Query for uncovered targets after the search stalled."""

    REPAIR = "repair"
    """Follow-up asking the LLM to fix its previous response."""

    OTHER = "other"
    """Any call outside the search (assertions, local search, ...)."""


class CallOutcome(str, enum.Enum):
    """How a logical LLM call ended."""

    OK = "ok"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CACHE_HIT = "cache_hit"


_OUTCOME_STATISTICS: dict[CallOutcome, RuntimeVariable] = {
    CallOutcome.OK: RuntimeVariable.LLMCallsSucceeded,
    CallOutcome.FAILED: RuntimeVariable.LLMCallsFailed,
    CallOutcome.TIMEOUT: RuntimeVariable.LLMCallsTimedOut,
}


@dataclasses.dataclass
class CallUsage:
    """Usage of a single logical call, filled in by the client while it sends it."""

    input_tokens: int = 0
    output_tokens: int = 0
    retries: int = 0
    error: str | None = None
    """The last error raised while sending the request, if any."""
    timed_out: bool = False
    """Whether that last error was a timeout."""


@dataclasses.dataclass
class LLMCallRecord:
    """Everything that is known about one logical LLM call."""

    purpose: str
    prompt: list[dict[str, str]]
    targets: list[str] = dataclasses.field(default_factory=list)
    call_id: str = dataclasses.field(default_factory=lambda: uuid.uuid4().hex)
    timestamp: str = dataclasses.field(
        default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
    )
    response: str | None = None
    latency_seconds: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    retries: int = 0
    outcome: CallOutcome = CallOutcome.FAILED
    error: str | None = None
    deserialization: dict[str, Any] | None = None
    """Parse status and statement disposition counts, if the response was parsed."""
    repair_attempt: int = 0
    """0 for an original call, ``n`` for the ``n``-th repair of it."""
    parent_call_id: str | None = None
    """The call whose response a repair call asks the LLM to fix."""

    def to_json(self) -> str:
        """Serialises the record as a single JSON line.

        Returns:
            The JSON representation of the record.
        """
        data = dataclasses.asdict(self)
        data["outcome"] = self.outcome.value
        return json.dumps(data, ensure_ascii=False, default=str)


def track_outcome(outcome: CallOutcome) -> None:
    """Counts a finished call in the outcome runtime variables.

    Cache hits are counted by ``TotalLLMCacheHits`` instead, so succeeded, failed,
    timed-out calls and cache hits add up to the logical queries.

    Args:
        outcome: The outcome of the call.
    """
    variable = _OUTCOME_STATISTICS.get(outcome)
    if variable is not None:
        count(variable)


def count(variable: RuntimeVariable, value: float = 1) -> None:
    """Adds to a numeric runtime variable from any thread.

    Args:
        variable: The runtime variable.
        value: The value to add.
    """
    with _LOCK:
        stat.add_to_runtime_variable(variable, value)


def write_record(record: LLMCallRecord) -> None:
    """Appends a record to the trace file if tracing is enabled.

    Args:
        record: The record to write.
    """
    trace_dir = config.configuration.large_language_model.trace_dir
    if not trace_dir:
        return
    try:
        path = Path(trace_dir).expanduser().resolve()
        path.mkdir(parents=True, exist_ok=True)
        line = record.to_json() + "\n"
        with _LOCK, (path / TRACE_FILE_NAME).open(mode="a", encoding="utf-8") as file:
            file.write(line)
    except OSError:
        _logger.exception("Could not write LLM call trace to %s", trace_dir)
