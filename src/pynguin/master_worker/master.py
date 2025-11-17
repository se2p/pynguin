#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Master process manager for Pynguin's client-master architecture."""

from __future__ import annotations

import logging
import time

import multiprocess as mp
import multiprocess.connection as mp_conn

from pynguin import config
from pynguin.master_worker.worker import WorkerResult, WorkerReturnCode, WorkerTask, worker_main

_LOGGER = logging.getLogger(__name__)


class RunningTask:
    """Represents a running test generation task with its associated worker process."""

    _worker_process: mp.Process
    _task: WorkerTask
    _receiving_connection: mp_conn.Connection
    _start_time: float
    _restart_count: int = 0
    _force_subprocess_mode: bool = False

    def __init__(
        self,
        task: WorkerTask,
    ):
        """Initialize the running task.

        Args:
            task: The worker task details
        """
        self._start_worker(task)

    def _start_worker(self, task: WorkerTask) -> None:
        """Start a worker subprocess for the given task.

        Args:
            task: The worker task details
        """
        receiving_connection, sending_connection = mp.Pipe(duplex=False)
        process = mp.Process(
            target=worker_main,
            args=(task, sending_connection),
            name="PynguinWorker",
        )
        self._worker_process = process
        self._receiving_connection = receiving_connection
        self._task = task
        self._start_time = time.time()
        _LOGGER.info("Starting new worker for task %s.", task.task_id)
        process.start()
        sending_connection.close()

    def _adjust_search_time_after_crash(self, elapsed_time: float) -> None:
        """Adjust the search time in config after a worker crash.

        There are no statistics for the used search_time, thus we need to use the elapsed
        time instead. Furthermore, using search_time might result in an endless
        setup-no_search-shutdown loop.

        Args:
            elapsed_time: Time consumed by the crashed worker
        """
        current_search_time = self._task.configuration.stopping.maximum_search_time
        if current_search_time > 0:
            # Reduce search time by elapsed time
            remaining_time = max(current_search_time - elapsed_time, 0.0)
            self._task.configuration.stopping.maximum_search_time = int(remaining_time)

            _LOGGER.info(
                "Adjusted maximum_search_time from %d to %d seconds "
                "(%.1f seconds consumed by crashed worker)",
                current_search_time,
                int(remaining_time),
                elapsed_time,
            )

    def _restart(self) -> bool:
        """Restart the worker process for this task.

        Returns:
            True if the worker process was restarted successfully, False otherwise
        """
        # Calculate elapsed time
        elapsed_time = time.time() - self._start_time
        self._adjust_search_time_after_crash(elapsed_time)

        if self._task.configuration.stopping.maximum_search_time <= 0:
            _LOGGER.warning("Maximum search time is zero, aborting")
            return False

        _LOGGER.warning("Worker process died, restarting (%d)", self._restart_count + 1)
        self._restart_count += 1

        if (
            self._restart_count >= 1
            and config.configuration.use_master_worker
            and not self._force_subprocess_mode
        ):
            _LOGGER.info("Enabling subprocess mode after worker crash for fault tolerance")
            self._force_subprocess_mode = True
            self._task.configuration.subprocess = True
            self._task.configuration.subprocess_if_recommended = False

        self._start_worker(self._task)
        return True

    def get_result(self) -> WorkerResult:
        """Get the result of the running task and restart the worker if necessary.

        Returns:
            Result from the worker process
        """
        try:
            result = self._receiving_connection.recv()
            self._receiving_connection.close()
            _LOGGER.info(
                "Received result for task %s: %s", result.task_id, result.worker_return_code
            )
            result.restart_count = self._restart_count
            return result

        except Exception:  # noqa: BLE001
            success = self._restart()
            if not success:
                return WorkerResult(
                    task_id=self._task.task_id,
                    worker_return_code=WorkerReturnCode.ERROR,
                    return_code=None,
                    error_message="Could not restart worker process",
                    restart_count=self._restart_count,
                )
            return self.get_result()

    def stop(self) -> None:
        """Stop the worker process for this task."""
        if self._worker_process and self._worker_process.is_alive():
            _LOGGER.info("Stopping worker")
            self._worker_process.terminate()
            self._worker_process.join(timeout=5)
            if self._worker_process.is_alive():
                _LOGGER.warning("Force killing worker")
                self._worker_process.kill()


class MasterProcess:
    """Master process that manages worker processes for test generation."""

    def __init__(self):
        """Initialize the master process."""
        self._running_tasks: dict[str, RunningTask] = {}

    def start_pynguin(self, configuration: config.Configuration) -> str:
        """Start a new task with the given configuration and returns its ID.

        Args:
            configuration: Configuration for the test generation task

        Returns:
            Task ID of the started task
        """
        task_id = f"test_gen_{time.time()}"
        task = WorkerTask(task_id=task_id, configuration=configuration)
        running_task = RunningTask(task=task)
        self._running_tasks[task_id] = running_task
        return task_id

    def get_result(self, task_id: str) -> WorkerResult:
        """Get the result of a running task and remove it from the running tasks.

        Args:
            task_id: ID of the task to get the result for

        Returns:
            Result from the worker process
        """
        if task_id not in self._running_tasks:
            return WorkerResult(
                task_id=task_id,
                worker_return_code=WorkerReturnCode.ERROR,
                return_code=None,
                error_message=f"Task {task_id} not found",
            )

        running_task = self._running_tasks[task_id]
        try:
            result = running_task.get_result()
            del self._running_tasks[task_id]
            return result
        except Exception as e:  # noqa: BLE001
            _LOGGER.error("Error getting result for task %s: %s", task_id, str(e))
            return WorkerResult(
                task_id=task_id,
                worker_return_code=WorkerReturnCode.ERROR,
                return_code=None,
                error_message=f"Error getting result: {e!s}",
            )

    def stop(self) -> None:
        """Stop all running tasks and remove them."""
        for task_id, running_task in self._running_tasks.items():
            _LOGGER.info("Stopping task %s", task_id)
            running_task.stop()
        self._running_tasks.clear()
