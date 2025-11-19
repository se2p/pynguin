#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Tests for the master process module."""

from unittest.mock import MagicMock

import pytest

from pynguin.master_worker.master import MasterProcess, RunningTask
from pynguin.master_worker.worker import WorkerReturnCode, WorkerTask
from tests.master_worker.test_worker import (
    sample_config,  # noqa: F401
    worker_task,  # noqa: F401
)


@pytest.fixture
def running_task(worker_task: WorkerTask) -> RunningTask:  # noqa: F811
    running_task = RunningTask(
        task=worker_task,
    )
    running_task._task = worker_task
    return running_task


@pytest.fixture
def master_and_config() -> tuple[MasterProcess, MagicMock]:
    master = MasterProcess()
    mock_config = MagicMock()
    mock_config.subprocess = False
    mock_config.subprocess_if_recommended = False
    mock_config.stopping.maximum_search_time = 100
    master._configuration = mock_config
    return master, mock_config


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


class FailingConnection:
    """Dummy connection class to simulate a failing receiving connection."""

    def recv(self):
        raise Exception("Simulated worker failure")

    def close(self):
        pass


def test_start_pynguin_with_restart(master_and_config):
    master, mock_config = master_and_config

    taskid = master.start_pynguin(mock_config)
    master._running_tasks[taskid]._receiving_connection = FailingConnection()
    result = master.get_result(taskid)

    assert result.restart_count == 1
    assert result.worker_return_code == WorkerReturnCode.OK


def test_start_pynguin_with_restart_out_of_time(master_and_config):
    master, mock_config = master_and_config
    mock_config.stopping.maximum_search_time = 0

    taskid = master.start_pynguin(mock_config)
    master._running_tasks[taskid]._receiving_connection = FailingConnection()
    result = master.get_result(taskid)

    assert result.restart_count == 0
    assert result.worker_return_code == WorkerReturnCode.ERROR
    assert "Could not restart worker process" in str(result.error)


def test_stop(master_and_config):
    master, mock_config = master_and_config

    taskid = master.start_pynguin(mock_config)

    master.stop()
    assert taskid not in master._running_tasks


def test_get_result_task_id_not_found(master_and_config):
    master, mock_config = master_and_config

    taskid = master.start_pynguin(mock_config)
    master.stop()

    result = master.get_result(taskid)
    assert result.worker_return_code == WorkerReturnCode.ERROR
    assert "not found" in str(result.error)
