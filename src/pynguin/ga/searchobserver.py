#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT

#  This file is part of Pynguin.
#
#
#  SPDX-License-Identifier: MIT
#
"""Provides an observer to observe the search."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pynguin.ga.testsuitechromosome as tsc


class SearchObserver(ABC):
    """Observes the execution of a search algorithm."""

    @abstractmethod
    def before_search_start(self, start_time_ns: int) -> None:
        """Called when the search starts.

        Args:
            start_time_ns: time since epoch in ns when the search started.
        """

    # TODO(fk) Unsure about API here, I mean we always produce a suite.

    @abstractmethod
    def before_first_search_iteration(self, initial: tsc.TestSuiteChromosome) -> None:
        """Called once before the very first iteration of the search algorithm.

        Calling this is optional, as not every approach has a result before
        the first iteration.

        Args:
            initial: The initially produced test suite.
        """

    @abstractmethod
    def after_search_iteration(self, best: tsc.TestSuiteChromosome) -> None:
        """Called after every iteration of the search algorithm.

        Args:
            best: The currently best produced test suite.
        """

    @abstractmethod
    def after_search_finish(self) -> None:
        """Called when the search has finished."""


class LogSearchObserver(SearchObserver):
    """Observes the search and creates some log output."""

    _logger = logging.getLogger(__name__)

    def __init__(self):  # noqa: D107
        self.iteration = 0

    def before_search_start(self, start_time_ns: int) -> None:  # noqa: D102
        self.iteration = 0

    def before_first_search_iteration(  # noqa: D102
        self, initial: tsc.TestSuiteChromosome
    ) -> None:
        self._logger.info("Initial Population, Coverage: %5f", initial.get_coverage())

    def after_search_iteration(  # noqa: D102
        self, best: tsc.TestSuiteChromosome
    ) -> None:
        self.iteration += 1
        self._logger.info("Iteration: %7i, Coverage: %5f", self.iteration, best.get_coverage())

    def after_search_finish(self) -> None:
        """Not used."""
