#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Master process manager for Pynguin's client-master architecture."""

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


@dataclass
class WorkerTask:
    """Task to be executed by a worker process."""

    task_id: str
    config_dict: dict[str, Any]

    def __post_init__(self):
        """Ensure task_id is unique if not provided."""
        if not self.task_id:
            self.task_id = f"task_{time.time()}_{id(self)}"


@dataclass
class WorkerResult:
    """Result from worker process execution."""

    task_id: str
    status: str  # 'success', 'error', 'timeout'
    return_code: int = 0
    error_message: str = ""
    traceback_str: str = ""


class MasterProcess:
    """Master process that manages worker processes for test generation."""

    def __init__(self):
        """Initialize master process."""
        self.task_queue: multiprocessing.Queue = multiprocessing.Queue()
        self.result_queue: multiprocessing.Queue = multiprocessing.Queue()
        self.worker_process: multiprocessing.Process | None = None
        self.restart_count = 0
        self.is_running = False
        self.monitor_thread: threading.Thread | None = None
        self._shutdown_event = threading.Event()

    def start_worker(self) -> bool:
        """Start or restart worker process.

        Returns:
            True if worker started successfully, False otherwise
        """
        try:
            if self.worker_process and self.worker_process.is_alive():
                _LOGGER.info("Terminating existing worker process")
                self.worker_process.terminate()
                self.worker_process.join(timeout=5)
                if self.worker_process.is_alive():
                    _LOGGER.warning("Force killing worker process")
                    self.worker_process.kill()

            _LOGGER.info("Starting new worker process")
            self.worker_process = multiprocessing.Process(
                target=worker_main, args=(self.task_queue, self.result_queue), name="PynguinWorker"
            )
            self.worker_process.start()

            # Give worker some time to start
            time.sleep(0.5)

            if self.worker_process.is_alive():
                _LOGGER.info(
                    "Worker process started successfully (PID: %d)", self.worker_process.pid
                )
                return True
            _LOGGER.error("Worker process failed to start")
            return False

        except Exception as e:  # noqa: BLE001
            _LOGGER.error("Failed to start worker process: %s", e)
            return False

    def submit_task(self, task: WorkerTask) -> bool:
        """Submit task to worker process.

        Args:
            task: Task to execute

        Returns:
            True if task was submitted successfully, False otherwise
        """
        try:
            if not self.is_running:
                _LOGGER.error("Master process is not running")
                return False

            if not self.worker_process or not self.worker_process.is_alive():
                _LOGGER.warning("Worker process is not alive, attempting restart")
                if not self.start_worker():
                    return False

            _LOGGER.info("Submitting task %s to worker", task.task_id)
            self.task_queue.put(task, timeout=5)
            return True

        except queue.Full:
            _LOGGER.error("Task queue is full")
            return False
        except Exception as e:  # noqa: BLE001
            _LOGGER.error("Failed to submit task: %s", e)
            return False

    def get_result(self, timeout: int | None = None) -> WorkerResult | None:
        """Get result from worker process.

        Args:
            timeout: Timeout in seconds, None for no timeout

        Returns:
            WorkerResult if available, None if timeout or error
        """
        try:
            result = self.result_queue.get()
            _LOGGER.info("Received result for task %s: %s", result.task_id, result.status)
            return result

        except queue.Empty:
            _LOGGER.warning("Timeout waiting for worker result")
            return WorkerResult(task_id="unknown", status="timeout", error_message="Worker timeout")
        except Exception as e:  # noqa: BLE001
            _LOGGER.error("Error getting result: %s", e)
            return WorkerResult(task_id="unknown", status="error", error_message=str(e))

    def start(self) -> bool:
        """Start the master process and worker monitoring.

        Returns:
            True if started successfully, False otherwise
        """
        if self.is_running:
            _LOGGER.warning("Master process is already running")
            return True

        _LOGGER.info("Starting master process")

        if not self.start_worker():
            return False

        self.is_running = True

        # Start monitoring thread
        self.monitor_thread = threading.Thread(
            target=self._monitor_worker, name="WorkerMonitor", daemon=True
        )
        self.monitor_thread.start()

        _LOGGER.info("Master process started successfully")
        return True

    def stop(self) -> None:
        """Stop the master process and clean up resources."""
        if not self.is_running:
            return

        _LOGGER.info("Stopping master process")
        self.is_running = False
        self._shutdown_event.set()

        # Stop worker process
        if self.worker_process and self.worker_process.is_alive():
            _LOGGER.info("Stopping worker process")
            self.worker_process.terminate()
            self.worker_process.join(timeout=5)
            if self.worker_process.is_alive():
                _LOGGER.warning("Force killing worker process")
                self.worker_process.kill()

        # Wait for monitor thread
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=2)

        _LOGGER.info("Master process stopped")

    def _monitor_worker(self) -> None:
        """Monitor worker process health and restart if necessary."""
        _LOGGER.info("Starting worker monitoring")

        while self.is_running and not self._shutdown_event.is_set():
            try:
                if not self.worker_process or not self.worker_process.is_alive():
                    _LOGGER.warning("Worker process died, restarting (%d)", self.restart_count + 1)
                    self.restart_count += 1

                    if not self.start_worker():
                        _LOGGER.error("Failed to restart worker process")
                        break

                # Check every second
                if self._shutdown_event.wait(1):
                    break

            except Exception as e:  # noqa: BLE001
                _LOGGER.error("Error in worker monitoring: %s", e)
                break

        _LOGGER.info("Worker monitoring stopped")


def worker_main(task_queue: multiprocessing.Queue, result_queue: multiprocessing.Queue) -> None:
    """Main function for worker process.

    Args:
        task_queue: Queue to receive tasks from master
        result_queue: Queue to send results back to master
    """

    # Set up signal handlers for graceful shutdown
    def signal_handler(signum, _):
        _LOGGER.info("Worker process received signal %d, shutting down", signum)
        sys.exit(0)

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

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
