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

    _logger = logging.getLogger(__name__)

    def __init__(self):
        """Creates a new LocalSearchTimer instance."""
        self._end_time = 0
        self._logger = logging.getLogger(__name__)

    def start_timer(self) -> None:
        """Starts the local search timer."""
        start_time = int(time.perf_counter()) * 1000
        self._end_time = start_time + config.configuration.local_search.local_search_time
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
            self._end_time,
        )
        return current_time > self._end_time
