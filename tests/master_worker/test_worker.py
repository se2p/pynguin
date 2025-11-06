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

import pytest

import pynguin.configuration as config

from pynguin.generator import ReturnCode
from pynguin.master_worker.worker import LogRecord
from pynguin.master_worker.worker import WorkerResult
from pynguin.master_worker.worker import WorkerReturnCode
from pynguin.master_worker.worker import WorkerTask


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
    return WorkerResult(
        task_id="test_task", worker_return_code=WorkerReturnCode.OK, return_code=ReturnCode.OK
    )


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


@pytest.mark.parametrize(
    "task_id,worker_return_code,return_code,error_message,traceback_str",
    [
        (
            "test_task",
            WorkerReturnCode.ERROR,
            ReturnCode.SETUP_FAILED,
            "Test error",
            "Test traceback",
        ),
        (
            "another_task",
            WorkerReturnCode.TIMEOUT,
            ReturnCode.NO_TESTS_GENERATED,
            "Timeout error",
            "Timeout traceback",
        ),
        ("third_task", WorkerReturnCode.OK, ReturnCode.OK, "", ""),
    ],
)
def test_worker_result_custom_values(
    task_id, worker_return_code, return_code, error_message, traceback_str
):
    """Test WorkerResult initialization with custom values."""
    result = WorkerResult(
        task_id=task_id,
        worker_return_code=worker_return_code,
        return_code=return_code,
        error_message=error_message,
        traceback_str=traceback_str,
    )

    assert result.task_id == task_id
    assert result.worker_return_code == worker_return_code
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
