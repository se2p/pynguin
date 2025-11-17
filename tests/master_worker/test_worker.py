#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Tests for the worker module."""

import logging
from unittest.mock import MagicMock, patch

import pytest

import pynguin.configuration as config
from pynguin.generator import ReturnCode
from pynguin.master_worker.worker import (
    WorkerError,
    WorkerLogFormatter,
    WorkerResult,
    WorkerReturnCode,
    WorkerTask,
    worker_main,
)


@pytest.fixture
def sample_config() -> config.Configuration:
    """Sample configuration."""
    return config.configuration


@pytest.fixture
def worker_task(sample_config: config.Configuration) -> WorkerTask:
    """Sample worker task."""
    return WorkerTask(task_id="test_task", configuration=sample_config)


def test_worker_log_formatter_format():
    formatter = WorkerLogFormatter()

    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="Test message",
        args=(),
        exc_info=None,
    )

    result = formatter.format(record)
    assert result.startswith("[Worker-")
    assert "Test message" in result


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
        ("third_task", WorkerReturnCode.OK, ReturnCode.OK, "", ""),
    ],
)
def test_worker_result_custom_values(
    task_id, worker_return_code, return_code, error_message, traceback_str
):
    """Test WorkerResult initialization with custom values."""
    error = None
    if error_message or traceback_str:
        error = WorkerError(error_message, traceback_str)

    result = WorkerResult(
        task_id=task_id,
        worker_return_code=worker_return_code,
        return_code=return_code,
        error=error,
    )

    assert result.task_id == task_id
    assert result.worker_return_code == worker_return_code
    assert result.return_code == return_code
    if error:
        assert result.error.traceback_str == traceback_str
        assert result.error == error
    else:
        assert result.error is None


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


def test_worker_main():
    worker_task = WorkerTask(task_id="test_task", configuration=config.configuration)
    sending_connection = MagicMock()
    worker_main(worker_task, sending_connection)

    sending_connection.send.assert_called_once()


def test_worker_main_keyboardinterrupt():
    worker_task = WorkerTask(task_id="test_task", configuration=config.configuration)
    sending_connection = MagicMock()
    with patch("pynguin.master_worker.worker.run_pynguin", side_effect=KeyboardInterrupt):
        worker_main(worker_task, sending_connection)

    sending_connection.send.assert_not_called()


def test_worker_main_generic_exception():
    worker_task = WorkerTask(task_id="test_task", configuration=config.configuration)
    sending_connection = MagicMock()
    with patch("pynguin.master_worker.worker.run_pynguin", side_effect=Exception("Test exception")):
        worker_main(worker_task, sending_connection)

    sending_connection.send.assert_called_once()
    sent_result = sending_connection.send.call_args[0][0]
    assert sent_result.worker_return_code == WorkerReturnCode.OK
    assert "Test exception" in str(sent_result)
    assert sent_result.error.traceback_str


def test_worker_main_generic_exception_send_fails():
    worker_task = WorkerTask(task_id="test_task", configuration=config.configuration)
    sending_connection = MagicMock()
    sending_connection.send.side_effect = Exception("Send failed")
    with patch("pynguin.master_worker.worker.run_pynguin", side_effect=Exception("Test exception")):
        worker_main(worker_task, sending_connection)

    sending_connection.send.assert_called_once()
