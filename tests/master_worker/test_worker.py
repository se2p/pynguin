#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Tests for the worker module."""

import logging

from unittest.mock import MagicMock
from unittest.mock import Mock
from unittest.mock import patch

import multiprocess as mp
import pytest

import pynguin.configuration as config

from pynguin.master_worker.worker import LogRecord
from pynguin.master_worker.worker import WorkerResult
from pynguin.master_worker.worker import WorkerTask
from pynguin.master_worker.worker import worker_main


@pytest.fixture
def sample_config():
    """Sample configuration."""
    return config.configuration


@pytest.fixture
def worker_task(sample_config):
    """Sample worker task."""
    return WorkerTask(task_id="test_task", configuration=sample_config)


@pytest.fixture
def worker_result():
    """Sample worker result."""
    return WorkerResult(task_id="test_task", status="success", return_code=0)


@pytest.fixture
def log_record():
    """Sample log record."""
    return LogRecord(
        level=logging.INFO,
        msg="Test message",
        args=("arg1", "arg2"),
        name="test.module",
        created=123456789.0,
        worker_pid=12345,
    )


@pytest.fixture
def mock_queues():
    """Mock multiprocessing queues."""
    return {
        "task_queue": MagicMock(),
        "result_queue": MagicMock(),
        "log_queue": MagicMock(),
    }


@pytest.fixture
def mock_worker_setup():
    """Common mocks for worker_main setup functions."""
    with (
        patch("pynguin.master_worker.worker._setup_signal_handlers") as mock_signals,
        patch("pynguin.master_worker.worker._setup_worker_logging") as mock_logging,
        patch("pynguin.master_worker.worker.mp.current_process") as mock_process,
    ):
        mock_proc = Mock()
        mock_proc.pid = 12345
        mock_process.return_value = mock_proc

        yield {
            "signals": mock_signals,
            "logging": mock_logging,
            "process": mock_process,
        }


# Test WorkerResult dataclass
@pytest.mark.parametrize(
    "task_id,status,expected_defaults",
    [
        ("test_task", "success", {"return_code": 0, "error_message": "", "traceback_str": ""}),
        ("another_task", "error", {"return_code": 0, "error_message": "", "traceback_str": ""}),
    ],
)
def test_worker_result_default_values(task_id, status, expected_defaults):
    """Test WorkerResult initialization with default values."""
    result = WorkerResult(task_id=task_id, status=status)

    assert result.task_id == task_id
    assert result.status == status
    for attr, expected_value in expected_defaults.items():
        assert getattr(result, attr) == expected_value


@pytest.mark.parametrize(
    "task_id,status,return_code,error_message,traceback_str",
    [
        ("test_task", "error", 1, "Test error", "Test traceback"),
        ("another_task", "timeout", 2, "Timeout error", "Timeout traceback"),
        ("third_task", "success", 0, "", ""),
    ],
)
def test_worker_result_custom_values(task_id, status, return_code, error_message, traceback_str):
    """Test WorkerResult initialization with custom values."""
    result = WorkerResult(
        task_id=task_id,
        status=status,
        return_code=return_code,
        error_message=error_message,
        traceback_str=traceback_str,
    )

    assert result.task_id == task_id
    assert result.status == status
    assert result.return_code == return_code
    assert result.error_message == error_message
    assert result.traceback_str == traceback_str


def test_log_record_initialization(log_record):
    """Test LogRecord initialization."""
    assert log_record.level == logging.INFO
    assert log_record.msg == "Test message"
    assert log_record.args == ("arg1", "arg2")
    assert log_record.name == "test.module"
    assert log_record.created == 123456789.0
    assert log_record.worker_pid == 12345


# Test WorkerTask dataclass
def test_worker_task_initialization(worker_task, sample_config):
    """Test WorkerTask initialization."""
    assert worker_task.task_id == "test_task"
    assert worker_task.configuration == sample_config


@pytest.mark.parametrize("task_id", ["", None])
def test_worker_task_post_init_with_empty_task_id(task_id, sample_config):
    """Test WorkerTask post_init with empty task_id."""
    task = WorkerTask(task_id=task_id, configuration=sample_config)

    assert task.task_id.startswith("task_")
    assert task.configuration == sample_config


def test_worker_task_post_init_with_valid_task_id(sample_config):
    """Test WorkerTask post_init with valid task_id."""
    task = WorkerTask(task_id="valid_task", configuration=sample_config)

    assert task.task_id == "valid_task"
    assert task.configuration == sample_config


# Test worker_main function
@patch("pynguin.master_worker.worker._process_task")
def test_worker_main_normal_operation(mock_process_task, mock_worker_setup, mock_queues):
    """Test worker_main normal operation."""
    mock_process_task.side_effect = [True, True, KeyboardInterrupt()]

    worker_main(mock_queues["task_queue"], mock_queues["result_queue"], mock_queues["log_queue"])

    mock_worker_setup["signals"].assert_called_once()
    mock_worker_setup["logging"].assert_called_once_with(mock_queues["log_queue"])
    assert mock_process_task.call_count == 1


@patch("pynguin.master_worker.worker._process_task")
def test_worker_main_keyboard_interrupt(mock_process_task, mock_worker_setup, mock_queues):
    """Test worker_main handles KeyboardInterrupt gracefully."""
    mock_process_task.side_effect = KeyboardInterrupt()

    worker_main(mock_queues["task_queue"], mock_queues["result_queue"], mock_queues["log_queue"])

    mock_worker_setup["signals"].assert_called_once()
    mock_worker_setup["logging"].assert_called_once_with(mock_queues["log_queue"])


@pytest.mark.parametrize(
    "exception_type,exception_msg",
    [
        (RuntimeError, "Unexpected error"),
        (ValueError, "Invalid value"),
        (OSError, "System error"),
    ],
)
@patch("pynguin.master_worker.worker._process_task")
def test_worker_main_handles_exceptions(
    mock_process_task, mock_worker_setup, mock_queues, exception_type, exception_msg
):
    """Test worker_main handles various exceptions."""
    mock_process_task.side_effect = exception_type(exception_msg)

    worker_main(mock_queues["task_queue"], mock_queues["result_queue"], mock_queues["log_queue"])

    mock_worker_setup["signals"].assert_called_once()
    mock_worker_setup["logging"].assert_called_once_with(mock_queues["log_queue"])


@patch("pynguin.master_worker.worker._process_task")
def test_worker_main_exception_recovery(mock_process_task, mock_worker_setup, mock_queues):
    """Test worker_main recovers from exceptions in task processing."""
    mock_process_task.side_effect = [
        RuntimeError("Task processing error"),
        True,
        KeyboardInterrupt(),
    ]

    worker_main(mock_queues["task_queue"], mock_queues["result_queue"], mock_queues["log_queue"])

    mock_worker_setup["signals"].assert_called_once()
    mock_worker_setup["logging"].assert_called_once_with(mock_queues["log_queue"])
    assert mock_process_task.call_count == 1


def test_worker_main_with_real_queues(sample_config, mock_worker_setup):
    """Test worker_main with actual multiprocessing queues."""
    task_queue = mp.Queue()
    result_queue = mp.Queue()
    log_queue = mp.Queue()

    sample_task = WorkerTask(task_id="integration_test", configuration=sample_config)
    task_queue.put(sample_task)

    with (
        patch("pynguin.master_worker.worker._execute_task") as mock_execute,
        patch("pynguin.master_worker.worker._process_task") as mock_process_task,
    ):
        mock_execute.return_value = WorkerResult(
            task_id="integration_test",
            status="success",
            return_code=0,
        )
        mock_process_task.side_effect = [True, KeyboardInterrupt()]

        worker_main(task_queue, result_queue, log_queue)

    mock_worker_setup["signals"].assert_called_once()
    mock_worker_setup["logging"].assert_called_once_with(log_queue)
