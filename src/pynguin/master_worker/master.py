#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Master process manager for Pynguin's client-master architecture."""

from __future__ import annotations

import logging
import queue
import threading
import time

import multiprocess as mp

from pynguin import config
from pynguin.master_worker.worker import WorkerResult
from pynguin.master_worker.worker import WorkerTask
from pynguin.master_worker.worker import worker_main


_LOGGER = logging.getLogger(__name__)

DEFAULT_WORKER_ID = 10000


class MasterProcess:
    """Master process that manages worker processes for test generation."""

    def __init__(self):
        """Initialize the master process."""
        # A queue to send the task (run_pynguin) to the worker process
        self._task_queue: mp.Queue = mp.Queue()
        # A queue to receive log records from the worker process
        self._log_queue: mp.Queue = mp.Queue()
        # A queue to receive results from the worker process. Must not be re-initialized.
        self._result_queue: mp.Queue = mp.Queue()
        # Reference to the current worker process, if any
        self._worker_process: mp.Process | None = None
        # Thread to forward logs from the worker to the master
        self._log_listener_thread: threading.Thread | None = None
        # Thread to restart the worker process if it crashes
        self._monitor_thread: threading.Thread | None = None
        # Event to signal shutdown of the master process and worker process
        self._shutdown_event = threading.Event()

        self._is_running = False
        self._restart_count = 0
        self._current_task_start_time = None
        self._force_subprocess_mode = False
        self._configuration: config.Configuration | None = None

    @property
    def is_running(self) -> bool:
        """Whether the master process is running."""
        return self._is_running

    def _adjust_search_time_after_crash(self, elapsed_time: float) -> None:
        """Adjust the search time in config after a worker crash.

        There are no statistics for the used search_time, thus we need to use the elapsed
        time instead. Furthermore, using search_time might result in an endless
        setup-no_search-shutdown loop.

        Args:
            elapsed_time: Time consumed by the crashed worker
        """
        if not self._configuration:
            return

        current_search_time = self._configuration.stopping.maximum_search_time
        if current_search_time > 0:
            # Reduce search time by elapsed time
            remaining_time = max(current_search_time - elapsed_time, 0.0)
            self._configuration.stopping.maximum_search_time = int(remaining_time)

            _LOGGER.info(
                "Adjusted maximum_search_time from %d to %d seconds "
                "(%.1f seconds consumed by crashed worker)",
                current_search_time,
                int(remaining_time),
                elapsed_time,
            )

    def start_worker(self) -> bool:
        """Start or restart a worker process.

        Returns:
            True if a worker started successfully, False otherwise
        """
        try:
            if self._worker_process and self._worker_process.is_alive():
                _LOGGER.info("Terminating existing worker process")
                self._worker_process.terminate()
                self._worker_process.join(timeout=5)
                if self._worker_process.is_alive():
                    _LOGGER.warning("Force killing worker process")
                    self._worker_process.kill()

            # Recreate log and task for fresh communication channels to the new worker
            _LOGGER.info("Recreating communication queues for new worker")
            self._task_queue = mp.Queue()
            self._log_queue = mp.Queue()
            # Do not re-create the result queue to ensure the client gets a result

            _LOGGER.info("Starting new worker process")
            self._worker_process = mp.Process(
                target=worker_main,
                args=(self._task_queue, self._result_queue, self._log_queue),
                name="PynguinWorker",
            )
            self._worker_process.start()

            # Give worker some time to start
            time.sleep(0.5)

            if self._worker_process.is_alive():
                _LOGGER.info(
                    "Worker process started successfully (PID: %d)", self._worker_process.pid
                )
                return True
            _LOGGER.error("Worker process failed to start")
            return False

        except Exception as e:  # noqa: BLE001
            _LOGGER.error("Failed to start worker process: %s", e)
            return False

    def run(self, configuration: config.Configuration) -> bool:
        """Run the task by submitting an (initial) worker task (run_pynguin).

        `_monitor_worker` will monitor the worker process and restart it if necessary
        by calling this method again.

        Args:
            configuration: Configuration for the test generation task to queue

        Returns:
            True if the task was submitted successfully, False otherwise
        """
        self._configuration = configuration
        try:
            if not self._is_running:
                _LOGGER.error("Master process is not running")
                return False

            if not self._worker_process or not self._worker_process.is_alive():
                _LOGGER.warning("Worker process is not alive, attempting restart")
                if not self.start_worker():
                    return False

            # Override subprocess mode in the task config if we're forcing it
            if self._force_subprocess_mode:
                self._configuration.subprocess = True
                self._configuration.subprocess_if_recommended = False
                _LOGGER.debug("Forcing subprocess mode.")

            task = WorkerTask(task_id=f"test_gen_{time.time()}", configuration=configuration)
            self._current_task_start_time = time.time()
            _LOGGER.info("Submitting task %s to worker", task.task_id)
            self._task_queue.put(task, timeout=5)
            return True

        except queue.Full:
            _LOGGER.error("Task queue is full")
            return False
        except Exception as e:  # noqa: BLE001
            _LOGGER.error("Failed to submit task: %s", e)
            return False

    def get_result(self) -> WorkerResult:
        """Get result from the worker process.

        Returns:
            Result from the worker process
        """
        try:
            result = self._result_queue.get()
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

        An initial worker task must be submitted separately by calling `run`.

        Returns:
            True if started successfully, False otherwise
        """
        if self._is_running:
            _LOGGER.warning("Master process is already running")
            return True

        _LOGGER.info("Starting master process")

        if not self.start_worker():
            return False

        self._is_running = True

        # Start the monitoring thread
        self._monitor_thread = threading.Thread(
            target=self._monitor_worker, name="WorkerMonitor", daemon=True
        )
        self._monitor_thread.start()

        # Start the log listener thread
        self._log_listener_thread = threading.Thread(
            target=self._log_listener, name="LogListener", daemon=True
        )
        self._log_listener_thread.start()

        _LOGGER.info("Master process started successfully")
        return True

    def stop(self) -> None:
        """Stop the master process and clean up resources."""
        if not self._is_running:
            return

        _LOGGER.info("Stopping master process")
        self._is_running = False
        self._shutdown_event.set()

        # Stop the worker process
        if self._worker_process and self._worker_process.is_alive():
            _LOGGER.info("Stopping worker process")
            self._worker_process.terminate()
            self._worker_process.join(timeout=5)
            if self._worker_process.is_alive():
                _LOGGER.warning("Force killing worker process")
                self._worker_process.kill()

        # Wait for monitor thread
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=2)

        # Wait for the log listener thread
        if self._log_listener_thread and self._log_listener_thread.is_alive():
            self._log_listener_thread.join(timeout=2)

        _LOGGER.info("Master process stopped")

    def _monitor_worker(self) -> None:  # noqa: C901 # TODO
        """Monitor worker process health and restart if necessary."""
        _LOGGER.info("Starting worker monitoring")

        while self._is_running and not self._shutdown_event.is_set():
            try:
                if not self._worker_process or not self._worker_process.is_alive():
                    if self._configuration is None:
                        _LOGGER.error("No configuration set, aborting")
                        break

                    # Calculate elapsed time if we have a start time
                    if self._current_task_start_time is not None:
                        elapsed_time = time.time() - self._current_task_start_time
                        self._adjust_search_time_after_crash(elapsed_time)

                    if self._configuration.stopping.maximum_search_time <= 0:
                        _LOGGER.warning("Maximum search time is zero, aborting")
                        self._result_queue.put(
                            WorkerResult(
                                task_id="unknown",
                                status="timeout",
                                error_message="Maximum search time reached after worker crash",
                            )
                        )
                        break

                    _LOGGER.warning("Worker process died, restarting (%d)", self._restart_count + 1)
                    self._restart_count += 1

                    if (
                        self._restart_count >= 1
                        and config.configuration.use_master_worker
                        and config.configuration.subprocess_if_recommended
                        and not self._force_subprocess_mode
                    ):
                        _LOGGER.info(
                            "Enabling subprocess mode after worker crash for fault tolerance"
                        )
                        self._force_subprocess_mode = True

                    if not self.start_worker():
                        _LOGGER.error("Failed to restart worker process")
                        break

                    # Record the start time for the new task
                    self._current_task_start_time = time.time()

                    if not self.run(config.configuration):
                        _LOGGER.error("Failed to submit test generation task")
                        break

                # Check every second
                if self._shutdown_event.wait(1):
                    break

            except Exception as e:  # noqa: BLE001
                _LOGGER.error("Error in worker monitoring: %s", e)
                break

        _LOGGER.info("Worker monitoring stopped")

    def _log_listener(self) -> None:
        """Listen for log records from a worker process and log them in master."""
        _LOGGER.info("Starting log listener")

        try:
            while self._is_running and not self._shutdown_event.is_set():
                try:
                    log_records = self._log_queue.get(timeout=0.1)
                except queue.Empty:
                    continue

                try:
                    for log_record in log_records:
                        worker_logger = logging.getLogger(f"worker.{log_record.name}")
                        formatted_msg = f"[Worker-{log_record.worker_pid}] {log_record.msg}"
                        worker_logger.log(log_record.level, formatted_msg, *log_record.args)
                except Exception as e:  # noqa: BLE001
                    _LOGGER.error("Error processing log record: %s", e)
                    continue
        except Exception as e:  # noqa: BLE001
            _LOGGER.error("Fatal error in log listener: %s", e)

        _LOGGER.info("Log listener stopped")
