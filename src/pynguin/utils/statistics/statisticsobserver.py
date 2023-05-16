#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2023 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides some observers for statistics."""
from __future__ import annotations

import time
import typing

import pynguin.ga.searchobserver as so
import pynguin.utils.statistics.statistics as stat

from pynguin.utils.statistics.runtimevariable import RuntimeVariable


if typing.TYPE_CHECKING:
    import pynguin.ga.testsuitechromosome as tsc


class IterationObserver(so.SearchObserver):
    """Observes the amount of iterations and logs them when the search
    has finished.
    """

    def __init__(self):
        self._iterations = 0

    def before_search_start(self, start_time_ns: int) -> None:
        pass

    def before_first_search_iteration(self, initial: tsc.TestSuiteChromosome) -> None:
        pass

    def after_search_iteration(self, best: tsc.TestSuiteChromosome) -> None:
        self._iterations += 1

    def after_search_finish(self) -> None:
        stat.track_output_variable(
            RuntimeVariable.AlgorithmIterations, self._iterations
        )


class SequenceStartTimeObserver(so.SearchObserver):
    """Sets the start time for sequence bases statistics."""

    def __init__(self):
        self._search_start_time_ns = 0

    def before_search_start(self, start_time_ns: int) -> None:
        stat.set_sequence_start_time(start_time_ns)
        self._search_start_time_ns = start_time_ns

    def before_first_search_iteration(self, initial: tsc.TestSuiteChromosome) -> None:
        pass

    def after_search_iteration(self, best: tsc.TestSuiteChromosome) -> None:
        pass

    def after_search_finish(self) -> None:
        stat.track_output_variable(
            RuntimeVariable.SearchTime, time.time_ns() - self._search_start_time_ns
        )


class BestIndividualObserver(so.SearchObserver):
    """Observes the best individual."""

    def before_search_start(self, start_time_ns: int) -> None:
        pass

    def before_first_search_iteration(self, initial: tsc.TestSuiteChromosome) -> None:
        stat.current_individual(initial)

    def after_search_iteration(self, best: tsc.TestSuiteChromosome) -> None:
        stat.current_individual(best)

    def after_search_finish(self) -> None:
        pass
