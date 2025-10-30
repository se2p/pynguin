#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Client interface for Pynguin's master-worker architecture."""

from __future__ import annotations

import logging
import time

from typing import TYPE_CHECKING

from pynguin.generator import ReturnCode
from pynguin.master import MasterProcess
from pynguin.master import WorkerTask
from pynguin.utils.configuration_writer import convert_config_to_dict


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
        self._started = False

    def start(self) -> bool:
        """Start the master-worker system.

        Returns:
            True if started successfully, False otherwise
        """
        if self._started:
            _LOGGER.warning("Client is already started")
            return True

        _LOGGER.info("Starting Pynguin client with master-worker architecture")

        if self.master.start():
            self._started = True
            _LOGGER.info("Pynguin client started successfully")
            return True
        _LOGGER.error("Failed to start Pynguin client")
        return False

    def stop(self) -> None:
        """Stop the master-worker system."""
        if not self._started:
            return

        _LOGGER.info("Stopping Pynguin client")
        self.master.stop()
        self._started = False
        _LOGGER.info("Pynguin client stopped")

    def generate_tests(self, timeout: int | None = None) -> ReturnCode:
        """Generate tests using the configured module.

        Args:
            timeout: Optional timeout in seconds for the generation

        Returns:
            ReturnCode indicating success or failure
        """
        if not self._started:
            _LOGGER.error("Client is not started. Call start() first.")
            return ReturnCode.SETUP_FAILED

        try:
            # Serialize configuration for worker
            config_dict = convert_config_to_dict(self.configuration)

            # Create task
            task = WorkerTask(task_id=f"test_gen_{time.time()}", config_dict=config_dict)

            # Submit task to worker
            if not self.master.submit_task(task):
                _LOGGER.error("Failed to submit test generation task")
                return ReturnCode.SETUP_FAILED

            # Wait for result
            result = self.master.get_result()

            if result is None:
                _LOGGER.error("No result received from worker")
                return ReturnCode.SETUP_FAILED

            if result.status == "success":
                _LOGGER.info("Test generation completed successfully")
                return ReturnCode(result.return_code)
            if result.status == "timeout":
                _LOGGER.error("Test generation timed out")
                return ReturnCode.SETUP_FAILED
            _LOGGER.error("Test generation failed: %s", result.error_message)
            if result.traceback_str:
                _LOGGER.debug("Worker traceback: %s", result.traceback_str)
            return ReturnCode.SETUP_FAILED

        except Exception as e:  # noqa: BLE001
            _LOGGER.error("Error during test generation: %s", e)
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
        return client.generate_tests()
