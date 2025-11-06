#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Master process manager for Pynguin's client-master architecture."""

from __future__ import annotations

import logging
import threading
import time

import multiprocess as mp
import multiprocess.connection as mp_conn

from pynguin import config
from pynguin.master_worker.worker import WorkerResult
from pynguin.master_worker.worker import WorkerReturnCode
from pynguin.master_worker.worker import WorkerTask
from pynguin.master_worker.worker import worker_main


_LOGGER = logging.getLogger(__name__)


class MasterProcess:
    """Master process that manages worker processes for test generation."""

    def __init__(self):
        """Initialize the master process."""
        # Connection to the worker process to receive results, if any
        self._receiving_connection: mp_conn.Connection | None = None
        # Reference to the current worker process, if any
        self._worker_process: mp.Process | None = None
        # Event to signal shutdown of the master process and worker process
        self._shutdown_event = threading.Event()

        self._restart_count = 0
        self._current_task_start_time = None
        self._force_subprocess_mode = False
        self._configuration: config.Configuration | None = None

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

    def _start_worker_with_task(self, task: WorkerTask) -> None:
        """Start a worker process with a task.

        Args:
            task: The task to run
        """
        receiving_connection, sending_connection = mp.Pipe(duplex=False)
        process = mp.Process(
            target=worker_main,
            args=(task, sending_connection),
            name="PynguinWorker",
        )
        self._worker_process = process
        self._receiving_connection = receiving_connection
        process.start()
        sending_connection.close()

    def start_pynguin(self, configuration: config.Configuration):
        """Start the initial task.

        Args:
            configuration: Configuration for the test generation task to queue

        Returns:
            True if the task was submitted successfully, False otherwise
        """
        self._configuration = configuration

        # Override subprocess mode in the task config if we're forcing it
        if self._force_subprocess_mode:
            self._configuration.subprocess = True
            self._configuration.subprocess_if_recommended = False
            _LOGGER.debug("Forcing subprocess mode.")

        task = WorkerTask(task_id=f"test_gen_{time.time()}", configuration=configuration)
        self._current_task_start_time = time.time()
        _LOGGER.info("Starting new worker.")
        self._start_worker_with_task(task)

    def get_result(self) -> WorkerResult:
        """Get result from the worker process.

        Returns:
            Result from the worker process
        """
        if self._receiving_connection is None:
            return WorkerResult(
                task_id="unknown",
                worker_return_code=WorkerReturnCode.ERROR,
                return_code=None,
                error_message="No worker process running",
            )

        try:
            result = self._receiving_connection.recv()
            self._receiving_connection.close()
            _LOGGER.info(
                "Received result for task %s: %s", result.task_id, result.worker_return_code
            )
            return result

        except Exception:  # noqa: BLE001
            self._restart_pynguin()
            return self.get_result()

    def _restart_pynguin(self):
        """Restart the worker process."""
        if self._configuration is None:
            _LOGGER.error("No configuration set, aborting")
            return

        # Calculate elapsed time if we have a start time
        if self._current_task_start_time is not None:
            elapsed_time = time.time() - self._current_task_start_time
            self._adjust_search_time_after_crash(elapsed_time)

        if self._configuration.stopping.maximum_search_time <= 0:
            _LOGGER.warning("Maximum search time is zero, aborting")
            return

        _LOGGER.warning("Worker process died, restarting (%d)", self._restart_count + 1)
        self._restart_count += 1

        if (
            self._restart_count >= 1
            and config.configuration.use_master_worker
            and config.configuration.subprocess_if_recommended
            and not self._force_subprocess_mode
        ):
            _LOGGER.info("Enabling subprocess mode after worker crash for fault tolerance")
            self._force_subprocess_mode = True

        # Record the start time for the new task
        self._current_task_start_time = time.time()

        self.start_pynguin(config.configuration)
