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

from abc import ABC
from abc import abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING

from pynguin.testcase import export


if TYPE_CHECKING:
    import pynguin.ga.testsuitechromosome as tsc

BEST_POPULATION_FILE_NAME = "best_population.py"


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


class BestPopulationObserver(SearchObserver):
    """Observes the search and stores the best individuals in a file."""

    _logger = logging.getLogger(__name__)

    def __init__(self, store_path: str):
        """Initialize the observer with the path to store the best population.

        Args:
            store_path: Path to the file where the best individuals will be stored.
        """
        self.store_path = Path(store_path + "/" + BEST_POPULATION_FILE_NAME)
        self.best_coverage = -1.0
        self.iteration = 0
        self.store_path.parent.mkdir(parents=True, exist_ok=True)

    def before_search_start(self, start_time_ns: int) -> None:  # noqa: D102
        self.iteration = 0
        self.best_coverage = -1.0
        self._logger.debug("Best population observer started, storing to: %s", self.store_path)

    def before_first_search_iteration(self, initial: tsc.TestSuiteChromosome) -> None:  # noqa: D102
        current_coverage = initial.get_coverage()
        if current_coverage > self.best_coverage:
            self.best_coverage = current_coverage
            self._store_best_population(initial)

    def after_search_iteration(self, best: tsc.TestSuiteChromosome) -> None:  # noqa: D102
        self.iteration += 1
        current_coverage = best.get_coverage()

        # Only store if this is better than our current best
        if current_coverage > self.best_coverage:
            self.best_coverage = current_coverage
            self._store_best_population(best)
            self._logger.debug(
                "New best individual found at iteration %d with coverage %5f, stored to %s",
                self.iteration,
                current_coverage,
                self.store_path,
            )

    def after_search_finish(self) -> None:  # noqa: D102
        self._logger.debug("Best population observer finished")

    def _store_best_population(self, chromosome: tsc.TestSuiteChromosome) -> None:
        """Store the best population to the file.

        Args:
            chromosome: The chromosome containing the best individuals.
        """
        try:
            export_visitor = export.PyTestChromosomeToAstVisitor(store_call_return=False)
            chromosome.accept(export_visitor)
            export.save_module_to_file(
                export_visitor.to_module(), self.store_path, format_with_black=False
            )

        except Exception as e:  # noqa: BLE001
            self._logger.warning("Failed to store best population: %s", e)
