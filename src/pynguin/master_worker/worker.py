#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides a worker process for Pynguin's master-worker architecture."""

from __future__ import annotations

import enum
import logging
import time
import traceback
from dataclasses import dataclass
from typing import TYPE_CHECKING

import multiprocess as mp
import multiprocess.connection as mp_conn

from pynguin.generator import ReturnCode, run_pynguin, set_configuration

if TYPE_CHECKING:
    import pynguin.configuration as config


_LOGGER = logging.getLogger(__name__)
DEFAULT_WORKER_ID = 10000


class WorkerLogFormatter(logging.Formatter):
    """Custom formatter that adds worker ID to log messages."""

    def __init__(self):
        """Initialize the formatter."""
        super().__init__()
        self.worker_pid = mp.current_process().pid or DEFAULT_WORKER_ID

    def format(self, record: logging.LogRecord) -> str:
        """Format the log record by adding the worker ID to the message.

        Args:
            record: The log record to format.

        Returns:
            The formatted log record.
        """
        original_msg = super().format(record)
        return f"[Worker-{self.worker_pid}] {original_msg}"


@enum.unique
class WorkerReturnCode(enum.IntEnum):
    """Return codes for master-worker communication."""

    OK = 0
    """Symbolises that there was no error with master-worker architecture."""

    ERROR = 1
    """Symbolises that an error occurred in master-worker architecture."""


class WorkerError(Exception):
    """Error that occurred during worker process execution."""

    def __init__(self, message="", traceback_str=""):
        """Initialize the error.

        Args:
            message: The error message.
            traceback_str: The traceback string.
        """
        super().__init__(message)
        self.traceback_str = traceback_str


@dataclass
class WorkerResult:
    """Result from worker process execution."""

    task_id: str
    worker_return_code: WorkerReturnCode
    return_code: ReturnCode | None
    error: WorkerError | None = None
    restart_count: int = 0

    @property
    def traceback_str(self) -> str:
        """Get traceback string from WorkerError if present."""
        return self.error.traceback_str if self.error else ""


@dataclass
class WorkerTask:
    """Task to be executed by a worker process."""

    task_id: str
    configuration: config.Configuration

    def __post_init__(self):
        """Ensure task_id is unique if not provided."""
        if not self.task_id:
            self.task_id = f"task_{time.time()}_{id(self)}"


def _setup_logging() -> None:
    """Set up logging for worker processes."""
    worker_formatter = WorkerLogFormatter()
    root_logger = logging.getLogger()
    for handler in root_logger.handlers:
        handler.setFormatter(worker_formatter)


def worker_main(
    task: WorkerTask,
    sending_connection: mp_conn.Connection,
) -> None:
    """Entry point for worker processes.

    Args:
        task: The task to be executed by the worker process.
        sending_connection: The connection to send results back to the master process.
    """
    try:
        _setup_logging()
        _LOGGER.info("Worker process started (PID: %d)", mp.current_process().pid)

        # Execute the task
        set_configuration(task.configuration)
        return_code = run_pynguin()
        result = WorkerResult(
            task_id=task.task_id, worker_return_code=WorkerReturnCode.OK, return_code=return_code
        )

        # Send result back
        sending_connection.send(result)
        _LOGGER.info("Worker completed task: %s", task.task_id)

    except KeyboardInterrupt:
        _LOGGER.info("Worker process interrupted")
    except Exception as e:  # noqa: BLE001
        task_id = "unknown"
        if "task" in locals() and hasattr(task, "task_id"):
            task_id = task.task_id

        error_result = WorkerResult(
            task_id=task_id,
            worker_return_code=WorkerReturnCode.OK,
            return_code=None,
            error=WorkerError(str(e), traceback.format_exc()),
        )
        try:
            sending_connection.send(error_result)
        except Exception:  # noqa: BLE001
            _LOGGER.error("Failed to send error result to master")
        _LOGGER.error("Pynguin error in worker process: %s\n%s", e, traceback.format_exc())
