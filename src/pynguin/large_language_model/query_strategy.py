# This file is part of Pynguin.
#
# SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
# SPDX-License-Identifier: MIT
#
"""Pluggable query strategy for LLM execution in search algorithms and workers."""

from __future__ import annotations

import abc
import concurrent.futures
import logging
from typing import TYPE_CHECKING, Any, TypeVar

if TYPE_CHECKING:
    from collections.abc import Callable

import pynguin.configuration as config
from pynguin.configuration import LLMMode

_T = TypeVar("_T")
_logger = logging.getLogger(__name__)


class LLMQueryStrategy(abc.ABC):
    """Abstract base class for LLM query execution strategies."""

    @abc.abstractmethod
    def execute(self, query_fn: Callable[[], _T]) -> _T | None:
        """Execute or dispatch an LLM query function.

        In synchronous mode, this calls `query_fn()` directly and returns the result.
        In asynchronous mode, this dispatches `query_fn` in the background (if none is
        currently in progress) and returns None immediately.

        Args:
            query_fn: The function that performs the query.

        Returns:
            The result if executed synchronously, or None if dispatched asynchronously or busy.
        """

    @abc.abstractmethod
    def poll(self) -> Any | None:
        """Poll for any completed asynchronous query result.

        Returns:
            The result if a background query has finished, or None if no result is available.
        """

    @abc.abstractmethod
    def is_in_progress(self) -> bool:
        """Return True if a query is currently running in the background."""

    @abc.abstractmethod
    def shutdown(self) -> None:
        """Clean up any background resources or workers."""


class SyncLLMQueryStrategy(LLMQueryStrategy):
    """Synchronous strategy that executes queries immediately and blocks."""

    def execute(self, query_fn: Callable[[], _T]) -> _T | None:
        """Execute the query function synchronously and return its result.

        Args:
            query_fn: The function that performs the query.

        Returns:
            The result of query_fn().
        """
        return query_fn()

    def poll(self) -> Any | None:
        """Poll returns None since synchronous queries complete immediately.

        Returns:
            Always None.
        """
        return None

    def is_in_progress(self) -> bool:
        """Synchronous queries are never in progress after execute() returns.

        Returns:
            Always False.
        """
        return False

    def shutdown(self) -> None:
        """No background resources to clean up in synchronous mode."""


class AsyncLLMQueryStrategy(LLMQueryStrategy):
    """Asynchronous non-blocking strategy that runs queries in the background on a worker."""

    def __init__(self, max_workers: int = 1) -> None:
        """Initialize the asynchronous query strategy.

        Args:
            max_workers: Maximum number of worker threads for background query execution.
        """
        self._executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix="PynguinLLMWorker"
        )
        self._future: concurrent.futures.Future[Any] | None = None

    def execute(self, query_fn: Callable[[], _T]) -> _T | None:
        """Dispatch the query function asynchronously in the background.

        Args:
            query_fn: The function that performs the query.

        Returns:
            None immediately (the result will be retrieved via poll()).
        """
        if self.is_in_progress():
            _logger.debug("Skipping LLM query: another query is already in progress.")
            return None
        self._future = self._executor.submit(query_fn)
        return None

    def poll(self) -> Any | None:
        """Poll for completed background query results.

        Returns:
            The result if a query has finished, else None.
        """
        if self._future is None:
            return None
        if not self._future.done():
            return None
        try:
            result = self._future.result()
        except Exception:
            _logger.exception("Background LLM query raised an exception.")
            result = None
        finally:
            self._future = None
        return result

    def is_in_progress(self) -> bool:
        """Whether a background query is currently executing.

        Returns:
            True if a background query is running, False otherwise.
        """
        return self._future is not None and not self._future.done()

    def shutdown(self) -> None:
        """Shut down background executor and cancel pending futures."""
        self._executor.shutdown(wait=True, cancel_futures=True)


def get_query_strategy(mode: LLMMode | str | None = None) -> LLMQueryStrategy:
    """Creates an LLMQueryStrategy instance according to the specified or configured mode.

    Args:
        mode: The desired LLMMode (SYNC or ASYNC), or a string ('sync' or 'async').
            If None, uses `config.configuration.large_language_model.llm_mode`.

    Returns:
        An LLMQueryStrategy instance (SyncLLMQueryStrategy or AsyncLLMQueryStrategy).
    """
    if mode is None:
        mode = getattr(config.configuration.large_language_model, "llm_mode", LLMMode.SYNC)
    mode_val = mode.lower() if isinstance(mode, str) else mode.value.lower()

    if mode_val == LLMMode.ASYNC.value.lower():
        return AsyncLLMQueryStrategy()
    return SyncLLMQueryStrategy()
