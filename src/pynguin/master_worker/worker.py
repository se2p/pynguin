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
import threading
import time
import traceback

from dataclasses import dataclass
from typing import Any

from pynguin.generator import run_pynguin
from pynguin.generator import set_configuration
from pynguin.utils.configuration_writer import read_config_from_dict


_LOGGER = logging.getLogger(__name__)
DEFAULT_WORKER_ID = 10000


class _QueueHandler(logging.Handler):
    """Logging handler that sends log records to a queue in batches."""

    def __init__(self, queue: multiprocessing.Queue):
        super().__init__()
        self.queue = queue
        self.worker_pid = multiprocessing.current_process().pid or DEFAULT_WORKER_ID
        self._buffer: list[LogRecord] = []
        self._buffer_lock = threading.Lock()
        self._flush_interval = 0.1  # seconds
        self._shutdown_event = threading.Event()

        self._flush_thread = threading.Thread(target=self._flusher, daemon=True)
        self._flush_thread.start()

    def _flusher(self) -> None:
        """Periodically flush the log buffer."""
        while not self._shutdown_event.wait(self._flush_interval):
            self.flush()

    def emit(self, record: logging.LogRecord) -> None:
        """Add a log record to the buffer."""
        try:
            log_record = LogRecord(
                level=record.levelno,
                msg=record.getMessage(),
                args=(),  # Already formatted in getMessage()
                name=record.name,
                created=record.created,
                worker_pid=self.worker_pid,
            )
            with self._buffer_lock:
                self._buffer.append(log_record)
        except Exception:  # noqa: BLE001
            # Cannot use logger here as it would cause recursion
            traceback.print_exc()

    def flush(self) -> None:
        """Send all buffered records to the queue."""
        if not self._buffer:
            return
        with self._buffer_lock:
            try:
                records_to_send = list(self._buffer)
                self._buffer.clear()
                if records_to_send:
                    self.queue.put(records_to_send)
            except Exception:  # noqa: BLE001
                traceback.print_exc()

    def close(self) -> None:
        """Flush the buffer and stop the flusher thread."""
        self._shutdown_event.set()
        self._flush_thread.join()
        self.flush()
        super().close()


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


def _setup_signal_handlers() -> None:
    """Set up signal handlers for graceful shutdown."""

    def signal_handler(signum, _):
        _LOGGER.info("Worker process received signal %d, shutting down", signum)
        sys.exit(0)

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)


def _setup_worker_logging(log_queue: multiprocessing.Queue) -> None:
    """Set up logging to forward logs to the master process."""
    # Add the queue handler to the root logger in the worker process
    queue_handler = _QueueHandler(log_queue)
    queue_handler.setLevel(logging.DEBUG)

    # Get the root logger and configure it properly
    root_logger = logging.getLogger()

    # Set the root logger level to DEBUG to capture all logs
    root_logger.setLevel(logging.DEBUG)

    # Add our queue handler
    root_logger.addHandler(queue_handler)


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


def _process_task(
    task_queue: multiprocessing.Queue,
    result_queue: multiprocessing.Queue,
) -> bool:
    """Process a single task from the queue.

    Returns:
        True if a task was processed, False if the queue was empty
    """
    try:
        # Wait for the initial task.
        task = task_queue.get(timeout=10)
        _LOGGER.info("Worker received task: %s", task.task_id)

        # Execute the task
        result = _execute_task(task)

        # Send result back
        result_queue.put(result)
        _LOGGER.info("Worker completed task: %s", task.task_id)
        return True

    except queue.Empty:
        _LOGGER.warning("Did not receive a task within the timeout period.")
        return False
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
        return True


def worker_main(
    task_queue: multiprocessing.Queue,
    result_queue: multiprocessing.Queue,
    log_queue: multiprocessing.Queue,
) -> None:
    """Entry point for worker processes.

    Args:
        task_queue: Queue to receive tasks from master
        result_queue: Queue to send results back to master
        log_queue: Queue to send log records back to master
    """
    root_logger = logging.getLogger()
    original_handlers = list(root_logger.handlers)

    try:
        _setup_signal_handlers()
        _setup_worker_logging(log_queue)
        _LOGGER.info("Worker process started (PID: %d)", multiprocessing.current_process().pid)

        # Process one task and then exit.
        if not _process_task(task_queue, result_queue):
            _LOGGER.warning("Worker did not receive a task and will exit.")

    except KeyboardInterrupt:
        _LOGGER.info("Worker process interrupted")
    except Exception as e:
        _LOGGER.exception("Worker process crashed: %s", e)
    finally:
        _LOGGER.info("Worker process exiting")
        # Explicitly close all logging handlers to ensure logs are flushed.
        for handler in logging.getLogger().handlers:
            handler.close()
        # Restore original handlers to avoid issues in tests
        root_logger.handlers = original_handlers
