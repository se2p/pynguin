#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides a worker process for Pynguin's master-worker architecture."""

from __future__ import annotations

import logging
import multiprocessing
import queue
import signal
import sys
import time
import traceback

from dataclasses import dataclass
from typing import Any

from pynguin.generator import run_pynguin
from pynguin.generator import set_configuration
from pynguin.utils.configuration_writer import read_config_from_dict


_LOGGER = logging.getLogger(__name__)
DEFAULT_WORKER_ID = 10000


@dataclass
class WorkerResult:
    """Result from worker process execution."""

    task_id: str
    status: str  # 'success', 'error', 'timeout'
    return_code: int = 0
    error_message: str = ""
    traceback_str: str = ""


@dataclass
class LogRecord:
    """Log record from a worker process."""

    level: int
    msg: str
    args: tuple
    name: str
    created: float
    worker_pid: int


@dataclass
class WorkerTask:
    """Task to be executed by a worker process."""

    task_id: str
    config_dict: dict[str, Any]

    def __post_init__(self):
        """Ensure task_id is unique if not provided."""
        if not self.task_id:
            self.task_id = f"task_{time.time()}_{id(self)}"


def worker_main(  # noqa: C901
    task_queue: multiprocessing.Queue,
    result_queue: multiprocessing.Queue,
    log_queue: multiprocessing.Queue,
) -> None:
    """Entry point for worker processes.

    TODO: simplify

    Args:
        task_queue: Queue to receive tasks from master
        result_queue: Queue to send results back to master
        log_queue: Queue to send log records back to master
    """

    # Set up signal handlers for graceful shutdown
    def signal_handler(signum, _):
        _LOGGER.info("Worker process received signal %d, shutting down", signum)
        sys.exit(0)

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    # Set up logging to forward logs to the master process
    class QueueHandler(logging.Handler):
        """Logging handler that sends log records to a queue."""

        def __init__(self, queue: multiprocessing.Queue):
            super().__init__()
            self.queue = queue
            self.worker_pid = multiprocessing.current_process().pid or DEFAULT_WORKER_ID

        def emit(self, record):
            """Send log record to the queue."""
            try:
                # Create a simple log record that can be pickled
                log_record = LogRecord(
                    level=record.levelno,
                    msg=record.getMessage(),
                    args=(),  # Already formatted in getMessage()
                    name=record.name,
                    created=record.created,
                    worker_pid=self.worker_pid,
                )
                self.queue.put_nowait(log_record)
            except Exception:
                _LOGGER.exception("Failed to send log record to master")

    # Add the queue handler to the root logger in the worker process
    queue_handler = QueueHandler(log_queue)
    queue_handler.setLevel(logging.DEBUG)

    # Get the root logger and configure it properly
    root_logger = logging.getLogger()

    # Set the root logger level to DEBUG to capture all logs
    root_logger.setLevel(logging.DEBUG)

    # Add our queue handler
    root_logger.addHandler(queue_handler)

    _LOGGER.info("Worker process started (PID: %d)", multiprocessing.current_process().pid)

    try:
        while True:
            try:
                # Get task from queue with timeout
                task = task_queue.get(timeout=1)
                _LOGGER.info("Worker received task: %s", task.task_id)

                # Execute the task
                result = _execute_task(task)

                # Send result back
                result_queue.put(result)
                _LOGGER.info("Worker completed task: %s", task.task_id)

            except queue.Empty:  # noqa: PERF203 TODO: remove?
                # Continue waiting for tasks
                continue
            except Exception as e:  # noqa: BLE001
                task_id = "unknown"
                if "task" in locals() and hasattr(task, "task_id"):
                    task_id = task.task_id

                error_result = WorkerResult(
                    task_id=task_id,
                    status="error",
                    error_message=str(e),
                    traceback_str=traceback.format_exc(),
                )
                try:
                    result_queue.put(error_result)
                except Exception:  # noqa: BLE001
                    _LOGGER.error("Failed to send error result to master")
                _LOGGER.error("Worker error: %s", e)

    except KeyboardInterrupt:
        _LOGGER.info("Worker process interrupted")
    except Exception as e:  # noqa: BLE001
        _LOGGER.error("Worker process crashed: %s", e)
    finally:
        _LOGGER.info("Worker process exiting")


def _execute_task(task: WorkerTask) -> WorkerResult:
    """Execute a test generation task.

    Args:
        task: Task to execute

    Returns:
        Result of task execution
    """
    try:
        # Deserialize configuration
        configuration = read_config_from_dict(task.config_dict)
        set_configuration(configuration)

        # Run test generation
        _LOGGER.info("Starting test generation for task %s", task.task_id)
        return_code = run_pynguin()

        return WorkerResult(task_id=task.task_id, status="success", return_code=return_code.value)

    except Exception as e:  # noqa: BLE001
        _LOGGER.error("Task execution failed: %s", e)
        return WorkerResult(
            task_id=task.task_id,
            status="error",
            error_message=str(e),
            traceback_str=traceback.format_exc(),
        )
