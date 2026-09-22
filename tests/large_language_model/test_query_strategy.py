# This file is part of Pynguin.
#
# SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
# SPDX-License-Identifier: MIT
#
from __future__ import annotations

import threading
import time

import pynguin.configuration as config
from pynguin.configuration import LLMMode
from pynguin.large_language_model.query_strategy import (
    AsyncLLMQueryStrategy,
    SyncLLMQueryStrategy,
    get_query_strategy,
)


def test_sync_strategy_execute():
    strategy = SyncLLMQueryStrategy()
    called = False

    def query_fn() -> str:
        nonlocal called
        called = True
        return "result"

    result = strategy.execute(query_fn)
    assert called is True
    assert result == "result"
    assert strategy.poll() is None
    assert strategy.is_in_progress() is False
    strategy.shutdown()


def test_async_strategy_execute_and_poll():
    strategy = AsyncLLMQueryStrategy()
    event = threading.Event()

    def query_fn() -> str:
        event.wait()
        return "async_result"

    try:
        assert strategy.is_in_progress() is False
        result = strategy.execute(query_fn)
        assert result is None
        assert strategy.is_in_progress() is True
        assert strategy.poll() is None

        # Trying to execute again while in progress should skip
        duplicate_called = False

        def dup_fn() -> str:
            nonlocal duplicate_called
            duplicate_called = True
            return "dup"

        assert strategy.execute(dup_fn) is None
        assert duplicate_called is False

        # Release worker and wait for completion
        event.set()
        timeout = time.time() + 5.0
        polled_result = None
        while time.time() < timeout:
            polled_result = strategy.poll()
            if polled_result is not None:
                break
            time.sleep(0.01)

        assert polled_result == "async_result"
        assert strategy.is_in_progress() is False
        assert strategy.poll() is None
    finally:
        strategy.shutdown()


def test_async_strategy_exception_handling():
    strategy = AsyncLLMQueryStrategy()

    def failing_query_fn():
        raise RuntimeError("API crash")

    try:
        strategy.execute(failing_query_fn)
        timeout = time.time() + 5.0
        while strategy.is_in_progress() and time.time() < timeout:
            time.sleep(0.01)

        # poll should return None and not crash
        assert strategy.poll() is None
        assert strategy.is_in_progress() is False
    finally:
        strategy.shutdown()


def test_async_strategy_shutdown_waits_for_running_task():
    strategy = AsyncLLMQueryStrategy()
    completed = False

    def slow_query_fn() -> str:
        time.sleep(0.05)
        nonlocal completed
        completed = True
        return "done"

    strategy.execute(slow_query_fn)
    assert strategy.is_in_progress() is True
    assert completed is False

    strategy.shutdown()
    assert completed is True


def test_get_query_strategy():
    assert isinstance(get_query_strategy(LLMMode.SYNC), SyncLLMQueryStrategy)
    assert isinstance(get_query_strategy("sync"), SyncLLMQueryStrategy)
    assert isinstance(get_query_strategy("SYNC"), SyncLLMQueryStrategy)

    async_strat = get_query_strategy(LLMMode.ASYNC)
    assert isinstance(async_strat, AsyncLLMQueryStrategy)
    async_strat.shutdown()

    async_strat_str = get_query_strategy("async")
    assert isinstance(async_strat_str, AsyncLLMQueryStrategy)
    async_strat_str.shutdown()

    # Default from config
    config.configuration.large_language_model.llm_mode = LLMMode.SYNC
    assert isinstance(get_query_strategy(), SyncLLMQueryStrategy)

    config.configuration.large_language_model.llm_mode = LLMMode.ASYNC
    async_strat_cfg = get_query_strategy()
    assert isinstance(async_strat_cfg, AsyncLLMQueryStrategy)
    async_strat_cfg.shutdown()
