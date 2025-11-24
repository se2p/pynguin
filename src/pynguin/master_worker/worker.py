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
from pynguin.utils.logging_utils import (
    WorkerFormatting,
)

if TYPE_CHECKING:
    import pynguin.configuration as config


_LOGGER = logging.getLogger(__name__)


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
        # separately needed for serialization and formatting
        self.traceback_str = traceback_str


@dataclass
class WorkerResult:
    """Result from worker process execution."""

    task_id: str
    worker_return_code: WorkerReturnCode
    return_code: ReturnCode | None
    # As the error is logged inside the worker, this is currently not used but
    # might be useful in the future.
    error: WorkerError | None = None
    restart_count: int = 0


@dataclass
class WorkerTask:
    """Task to be executed by a worker process."""

    task_id: str
    configuration: config.Configuration

    def __post_init__(self):
        """Ensure task_id is unique if not provided."""
        if not self.task_id:
            self.task_id = f"task_{time.time()}_{id(self)}"


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
        with WorkerFormatting():
            _LOGGER.info("Worker process started (PID: %d)", mp.current_process().pid)

            # Execute the task
            set_configuration(task.configuration)
            return_code = run_pynguin()
            result = WorkerResult(
                task_id=task.task_id,
                worker_return_code=WorkerReturnCode.OK,
                return_code=return_code,
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
            # from syntax does not work here
            error=WorkerError(str(e), traceback.format_exc()),
        )
        try:
            sending_connection.send(error_result)
        except Exception:  # noqa: BLE001
            _LOGGER.error("Failed to send error result to master")
        _LOGGER.error("Pynguin error in worker process: %s\n%s", e, traceback.format_exc())
