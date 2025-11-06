#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Tests for the master process module."""

import queue

from unittest.mock import Mock
from unittest.mock import patch

import pytest

import pynguin.configuration as config

from pynguin.master_worker.master import MasterProcess
from pynguin.master_worker.worker import WorkerReturnCode


@pytest.fixture
def sample_config():
    """Sample configuration."""
    return config.configuration


@pytest.fixture
def master_process(sample_config):
    """Create a MasterProcess instance for testing."""
    master_process = MasterProcess()
    master_process._configuration = sample_config
    return master_process


def test_master_process_init():
    """Test MasterProcess initialization."""
    master = MasterProcess()

    assert master._is_running is False
    assert master._restart_count == 0
    assert master._current_task_start_time is None
    assert master._force_subprocess_mode is False
    assert master._configuration is None
    assert master._worker_process is None
    assert master._log_listener_thread is None
    assert master._monitor_thread is None


def test_adjust_search_time_after_crash(master_process):
    """Test search time adjustment after worker crash."""
    master_process._configuration.stopping.maximum_search_time = 100

    master_process._adjust_search_time_after_crash(30.0)

    assert master_process._configuration.stopping.maximum_search_time == 70


def test_adjust_search_time_after_crash_minimum_zero(master_process):
    """Test search time adjustment doesn't go below zero."""
    master_process._configuration.stopping.maximum_search_time = 30

    master_process._adjust_search_time_after_crash(50.0)

    assert master_process._configuration.stopping.maximum_search_time == 0


@patch("time.time", return_value=123456.0)
def test_run_success(mock_time, master_process, sample_config):  # noqa: ARG001
    """Test successful task submission."""
    master_process._is_running = True
    master_process._worker_process = Mock()
    master_process._worker_process.is_alive.return_value = True
    master_process._task_queue = Mock()

    result = master_process.run(sample_config)

    assert result is True
    assert master_process._current_task_start_time == 123456.0


def test_run_not_running(master_process, sample_config):
    """Test run when master is not running."""
    master_process._is_running = False

    result = master_process.run(sample_config)

    assert result is False


def test_run_forces_subprocess_mode(master_process, sample_config):
    """Test run forces subprocess mode when enabled."""
    master_process._is_running = True
    master_process._force_subprocess_mode = True
    master_process._worker_process = Mock()
    master_process._worker_process.is_alive.return_value = True
    master_process._task_queue = Mock()

    result = master_process.run(sample_config)

    assert result is True
    assert master_process._configuration.subprocess is True
    assert master_process._configuration.subprocess_if_recommended is False


def test_get_result_exception(master_process):
    """Test result retrieval handles exceptions."""
    master_process._result_queue = Mock()
    master_process._result_queue.get.side_effect = Exception("Test error")

    result = master_process.get_result()

    assert result.worker_return_code == WorkerReturnCode.ERROR
    assert result.task_id == "unknown"


def test_start_already_running(master_process):
    """Test start when already running."""
    master_process._is_running = True

    result = master_process.start()

    assert result is True


def test_stop_success(master_process):
    """Test successful master stop."""
    master_process._is_running = True
    master_process._worker_process = Mock()
    master_process._worker_process.is_alive.return_value = True
    master_process._monitor_thread = Mock()
    master_process._monitor_thread.is_alive.return_value = True
    master_process._log_listener_thread = Mock()
    master_process._log_listener_thread.is_alive.return_value = True

    master_process.stop()

    assert master_process._is_running is False
    master_process._worker_process.terminate.assert_called_once()


def test_stop_not_running(master_process):
    """Test stop when not running."""
    master_process._is_running = False

    master_process.stop()  # Should not raise exception


def test_stop_kills_stuck_worker(master_process):
    """Test stop kills stuck worker process."""
    master_process._is_running = True
    master_process._worker_process = Mock()
    master_process._worker_process.is_alive.side_effect = [
        True,
        True,
    ]  # Alive before and after terminate

    master_process.stop()

    master_process._worker_process.terminate.assert_called_once()
    master_process._worker_process.kill.assert_called_once()


def test_log_listener_handles_empty_queue(master_process):
    """Test log listener handles empty queue."""
    master_process._is_running = True
    master_process._shutdown_event = Mock()
    master_process._shutdown_event.is_set.side_effect = [False, True]
    master_process._log_queue = Mock()
    master_process._log_queue.get.side_effect = queue.Empty()

    master_process._log_listener()  # Should not raise exception


def test_log_listener_handles_exception(master_process):
    """Test log listener handles exceptions."""
    master_process._is_running = True
    master_process._shutdown_event = Mock()
    master_process._shutdown_event.is_set.side_effect = [False, True]
    master_process._log_queue = Mock()
    master_process._log_queue.get.side_effect = Exception("Test error")

    master_process._log_listener()  # Should not raise exception


@patch("time.time")
@patch("pynguin.master_worker.master.mp.Process")
@patch("pynguin.master_worker.master.mp.Queue")
def test_integration(mock_queue, mock_process, mock_time, master_process, sample_config):  # noqa: ARG001
    """Test a full lifecycle of master process."""
    # Mock time for consistent task IDs
    mock_time.return_value = 123456.0

    # Mock process
    mock_process_instance = Mock()
    mock_process_instance.is_alive.return_value = True
    mock_process_instance.pid = 12345
    mock_process.return_value = mock_process_instance

    # Mock threading to avoid actual thread creation
    with patch("threading.Thread") as mock_thread:
        mock_thread_instance = Mock()
        mock_thread.return_value = mock_thread_instance

        # Start the master
        assert master_process.start() is True
        assert master_process._is_running is True

        # Run a task
        assert master_process.run(sample_config) is True

        # Stop the master
        master_process.stop()
        assert master_process._is_running is False
