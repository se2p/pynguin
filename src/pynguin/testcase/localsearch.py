#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
"""Provides the local search strategies."""
import abc
import logging
import time

import pynguin.configuration as config
from abc import ABC


from pynguin.ga.chromosome import Chromosome
from pynguin.ga.testcasechromosome import TestCaseChromosome
from pynguin.ga.testsuitechromosome import TestSuiteChromosome


class LocalSearch(ABC):
    """An abstract class for local search."""

    _logger = logging.getLogger(__name__)

    @abc.abstractmethod
    def local_search(self, chromosome:Chromosome) -> None:
        """Executes local search on the chromosome."""

class TestCaseLocalSearch(LocalSearch, ABC):

    def local_search(self, chromosome:TestCaseChromosome) -> None:
        for statement in chromosome.test_case.statements:
            if LocalSearchTimer.__new__(LocalSearchTimer).limit_reached():
                break
            #TODO: Local Search


class TestSuiteLocalSearch(LocalSearch, ABC):

    def local_search(self, chromosome:TestSuiteChromosome) -> None:
        pass #TODO



class LocalSearchTimer:
    """Manages the local search budget."""

    _instance = None

    def __new__(cls, *args, **kwargs):
        """Provides the instance, or creates a new instance."""
        if not cls._instance:
            cls._instance = super(LocalSearchTimer, cls).__new__(cls)
            cls._instance.end_time = 0
            cls._instance._logger = logging.getLogger(__name__)
        return cls._instance


    def start_local_search(self) -> None:
        """Starts the local search timer."""
        start_time = int(time.perf_counter()) * 1000
        self.end_time = start_time + config.LocalSearchConfiguration.local_search_time
        self._logger.debug("Local search started at %f ms", start_time)


    def limit_reached(self) -> bool:
        """Gives back information, if the local search limit is reached.

        Returns:
            Gives back True if the local search limit is reached."""
        current_time = int(time.perf_counter()) * 1000
        self._logger.debug(f"Checking limit: current time = %f, end time = %f", current_time,self.end_time)
        return current_time > self.end_time

