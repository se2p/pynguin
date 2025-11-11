#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Tests for the master process module."""

from unittest.mock import MagicMock
from unittest.mock import Mock

import pytest


from pynguin.master_worker.master import MasterProcess
from pynguin.master_worker.master import RunningTask
from pynguin.master_worker.worker import WorkerReturnCode
from pynguin.master_worker.worker import WorkerTask
from tests.master_worker.test_worker import sample_config # noqa: F401
from tests.master_worker.test_worker import worker_task # noqa: F401



@pytest.fixture
def running_task(worker_task: WorkerTask) -> RunningTask:
    running_task = RunningTask(
        worker_process=Mock(),
        task=worker_task,
        receiving_connection=Mock(),
    )
    running_task._task = worker_task
    return running_task


def test_adjust_search_time_after_crash(running_task):
    """Test search time adjustment after worker crash."""
    running_task._task.configuration.stopping.maximum_search_time = 100
    running_task._adjust_search_time_after_crash(30.0)
    assert running_task._task.configuration.stopping.maximum_search_time == 70


def test_adjust_search_time_after_crash_no_time_left(running_task):
    """Test search time adjustment when no time is left."""
    running_task._task.configuration.stopping.maximum_search_time = 0
    running_task._adjust_search_time_after_crash(30.0)
    assert running_task._task.configuration.stopping.maximum_search_time == 0


def test_adjust_search_time_after_crash_minimum_zero(running_task):
    """Test search time adjustment doesn't go below zero."""
    running_task._task.configuration.stopping.maximum_search_time = 30
    running_task._adjust_search_time_after_crash(50.0)
    assert running_task._task.configuration.stopping.maximum_search_time == 0


def test_start_pynguin_with_restart():
    master = MasterProcess()
    mock_config = MagicMock()
    mock_config.subprocess = False
    mock_config.subprocess_if_recommended = False
    mock_config.stopping.maximum_search_time = 100
    master._configuration = mock_config

    # Start the initial task
    taskid = master.start_pynguin(mock_config)

    # Simulate a receiving connection that raises on recv (simulate failure)
    class DummyConnection:
        def recv(self):
            raise Exception("Simulated worker failure")

        def close(self):
            pass

    master._receiving_connection = DummyConnection()
    result = master.get_result(taskid)

    assert result.worker_return_code == WorkerReturnCode.OK
