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
from pynguin.testcase.localsearchobjective import LocalSearchObjective
from pynguin.testcase.localsearchstatement import StatementLocalSearch

class LocalSearch(ABC):
    """An abstract class for local search."""

    _logger = logging.getLogger(__name__)

    @abc.abstractmethod
    def local_search(self, chromosome:Chromosome, objective: LocalSearchObjective | None) -> None:
        """Executes local search on the chromosome."""

class TestCaseLocalSearch(LocalSearch, ABC):

    def local_search(self, chromosome:TestCaseChromosome, objective: LocalSearchObjective) -> None:

        for i in range(chromosome.test_case.statements.__len__()-1, 0, -1):
            if LocalSearchTimer.__new__(LocalSearchTimer).limit_reached():
                return

            statement = chromosome.test_case.statements[i]
            local_search_statement = StatementLocalSearch.choose_local_search_statement(statement)

            if local_search_statement is not None:
                self._logger.debug("Local search statement found for the statement {}".format(statement))
                local_search_statement.search(chromosome, i, objective)
            else:
                self._logger.debug("No local search statement found for statement {}".format(statement))

class TestSuiteLocalSearch(LocalSearch, ABC):

    def local_search(self, chromosome:TestSuiteChromosome, objective: LocalSearchObjective | None = None) -> None:

        for i in range(0 ,chromosome.test_case_chromosomes.__len__()-1, 1):
            if LocalSearchTimer.get_instance().limit_reached():
                break

            objective = LocalSearchObjective(chromosome, i)

            # if randomness.next_float() <= config.LocalSearchConfiguration.local_search_probability: TODO: temporarily disabled for debugging purpose
            test_case_local_search = TestCaseLocalSearch()
            test_case_local_search.local_search(chromosome.get_test_case_chromosome(i), objective)

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
            Gives back True if the local search limit is reached."""
        current_time = int(time.perf_counter()) * 1000
        self._logger.debug(f"Checking limit: current time = %f, end time = %f", current_time,self.end_time)
        return current_time > self.end_time

