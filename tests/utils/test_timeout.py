#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
from __future__ import annotations

import threading
import time

import pytest

import pynguin.configuration as config
from pynguin.utils.timeout import (
    TestExecutionTimeoutError,
    resolve_module_timeout,
    resolve_timeout,
    time_limit,
)


def test_resolve_timeout():
    config.configuration.stopping.maximum_test_execution_timeout = 5
    assert resolve_timeout(10.0) == 10.0
    assert resolve_timeout(None) == 5


def test_resolve_module_timeout():
    config.configuration.stopping.maximum_module_execution_timeout = 5
    assert resolve_module_timeout(10.0) == 10.0
    assert resolve_module_timeout(None) == 5


def test_time_limit_success():
    with time_limit(2.0):
        val = 1 + 1
    assert val == 2


def test_time_limit_expires():
    with pytest.raises(TestExecutionTimeoutError), time_limit(0.1):
        time.sleep(1.0)


def test_time_limit_non_positive_disabled():
    with time_limit(0):
        val = 42
    assert val == 42

    with time_limit(-1):
        val = 43
    assert val == 43


def test_time_limit_off_main_thread():
    error_raised = False

    def worker():
        nonlocal error_raised
        try:
            with time_limit(0.1):
                # When not on main thread, time_limit does not install signal handler
                time.sleep(0.05)
        except TestExecutionTimeoutError:
            error_raised = True

    thread = threading.Thread(target=worker)
    thread.start()
    thread.join()
    assert not error_raised


def test_resolve_timeout_fallback(monkeypatch):
    monkeypatch.setattr(config.configuration, "stopping", None)
    assert resolve_timeout(None) == 5.0


def test_resolve_module_timeout_fallback(monkeypatch):
    monkeypatch.setattr(config.configuration, "stopping", None)
    assert resolve_module_timeout(None) == 5.0
