#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
"""Provides a timer which measures the time of local search."""

import logging
import time

import pynguin.configuration as config


class LocalSearchTimer:
    """Manages the local search budget."""

    _instance = None
    _logger: logging.Logger

    def __new__(cls):
        """Provides the instance, or creates a new instance."""
        if not cls._instance:
            cls._instance = super().__new__(cls)
            cls._instance.end_time = 0
            cls._instance._logger = logging.getLogger(__name__)  # noqa: SLF001
        return cls._instance

    @classmethod
    def get_instance(cls):
        """Provides the instance.

        Returns: The instance of LocalSearchTimer.
        """
        return cls()

    def start_local_search(self) -> None:
        """Starts the local search timer."""
        start_time = int(time.perf_counter()) * 1000
        self.end_time = start_time + config.LocalSearchConfiguration.local_search_time
        self._logger.debug("Local search started at %f ms", start_time)

    def limit_reached(self) -> bool:
        """Gives back information, if the local search limit is reached.

        Returns:
            Gives back True if the local search limit is reached.
        """
        current_time = int(time.perf_counter()) * 1000
        self._logger.debug(
            "Checking limit: current time = %f, end time = %f",
            current_time,
            self.end_time,
        )
        return current_time > self.end_time
