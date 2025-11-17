#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Client interface for Pynguin's master-worker architecture."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from pynguin.generator import ReturnCode
from pynguin.master_worker.master import MasterProcess
from pynguin.master_worker.worker import WorkerReturnCode

if TYPE_CHECKING:
    import pynguin.configuration as config


_LOGGER = logging.getLogger(__name__)


class PynguinClient:
    """Client interface for running Pynguin with master-worker architecture."""

    def __init__(self, configuration: config.Configuration):
        """Initialize Pynguin client.

        Args:
            configuration: Pynguin configuration
        """
        self.configuration = configuration
        self.master = MasterProcess()

    @staticmethod
    def start() -> None:
        """Start the master-worker system."""
        _LOGGER.info("Starting Pynguin client with master-worker architecture")

    def stop(self) -> None:
        """Stop the master-worker system."""
        _LOGGER.info("Stopping master-worker system")
        self.master.stop()
        _LOGGER.info("Master-worker system stopped")

    def run_pynguin(self) -> ReturnCode:
        """Run Pynguin with master-worker architecture.

        Returns:
            ReturnCode indicating success or failure
        """
        try:
            task_id = self.master.start_pynguin(self.configuration)

            # Wait for a result
            result = self.master.get_result(task_id)

            if result is None:
                _LOGGER.error("No result received from worker")
                return ReturnCode.NO_TESTS_GENERATED

            match result.worker_return_code:
                case WorkerReturnCode.ERROR:
                    _LOGGER.error("Worker process crashed")
                    return ReturnCode.NO_TESTS_GENERATED
                case WorkerReturnCode.TIMEOUT:
                    _LOGGER.error("Worker process timed out")
                    return ReturnCode.NO_TESTS_GENERATED
                case WorkerReturnCode.OK:
                    if result.return_code is None:
                        _LOGGER.error("Worker process returned without error code")
                        return ReturnCode.NO_TESTS_GENERATED
                    return result.return_code

        except Exception as e:  # noqa: BLE001
            _LOGGER.error("Error in master-worker architecture: %s", e)
            return ReturnCode.SETUP_FAILED

    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()


def run_pynguin_with_master_worker(configuration: config.Configuration) -> ReturnCode:
    """Run Pynguin with master-worker architecture.

    This is a convenience function that handles the complete lifecycle
    of the master-worker system for a single test generation run.

    Args:
        configuration: Pynguin configuration

    Returns:
        ReturnCode indicating success or failure
    """
    with PynguinClient(configuration) as client:
        return client.run_pynguin()
