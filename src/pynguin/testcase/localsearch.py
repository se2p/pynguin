#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
"""Provides the local search strategies."""
from __future__ import annotations

import abc
import logging

from abc import ABC


from pynguin.ga.chromosome import Chromosome
from pynguin.ga.testcasechromosome import TestCaseChromosome
from pynguin.ga.testsuitechromosome import TestSuiteChromosome
from pynguin.testcase.localsearchobjective import LocalSearchObjective
from pynguin.testcase.localsearchstatement import StatementLocalSearch
from pynguin.testcase.localsearchtimer import LocalSearchTimer
from pynguin.testcase.statement import EnumPrimitiveStatement
from pynguin.testcase.testfactory import TestFactory


class LocalSearch(ABC):
    """An abstract class for local search."""

    _logger = logging.getLogger(__name__)

    @abc.abstractmethod
    def local_search(self, chromosome:Chromosome, factory: TestFactory, objective: LocalSearchObjective | None) -> None:
        """Executes local search on the chromosome."""

class TestCaseLocalSearch(LocalSearch, ABC):

    def local_search(self, chromosome:TestCaseChromosome, factory: TestFactory, objective: LocalSearchObjective) -> None:

        for i in range(chromosome.test_case.statements.__len__()-1, 0, -1):
            if LocalSearchTimer.get_instance().limit_reached():
                return

            statement = chromosome.test_case.statements[i]
            local_search_statement = StatementLocalSearch.choose_local_search_statement(statement)

            if local_search_statement is not None:
                self._logger.debug("Local search statement found for the statement {}".format(statement))
                local_search_statement.search(chromosome, i, objective, factory)

class TestSuiteLocalSearch(LocalSearch, ABC):

    def local_search(self, chromosome:TestSuiteChromosome,factory: TestFactory, objective: LocalSearchObjective | None = None) -> None:

        for i in range(0 ,chromosome.test_case_chromosomes.__len__()-1, 1):
            if LocalSearchTimer.get_instance().limit_reached():
                break

            objective = LocalSearchObjective(chromosome, i)

            # if randomness.next_float() <= config.LocalSearchConfiguration.local_search_probability: TODO: temporarily disabled for debugging purpose
            test_case_local_search = TestCaseLocalSearch()
            test_case_local_search.local_search(chromosome.get_test_case_chromosome(i), factory, objective)

