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
from pynguin.testcase.testfactory import TestFactory


class LocalSearch(ABC):
    """An abstract class for local search."""

    _logger = logging.getLogger(__name__)

    @abc.abstractmethod
    def local_search(
        self,
        chromosome: Chromosome,
        factory: TestFactory,
        objective: LocalSearchObjective | None,
    ) -> None:
        """Executes local search on the chromosome."""


class TestCaseLocalSearch(LocalSearch, ABC):

    def local_search( # noqa: D102
        self,
        chromosome: Chromosome,
        factory: TestFactory,
        objective: LocalSearchObjective | None,
    ) -> None:
        assert isinstance(chromosome, TestCaseChromosome)
        assert objective is not None

        for i in range(chromosome.test_case.statements.__len__() - 1, 0, -1):
            if LocalSearchTimer.get_instance().limit_reached():
                return

            statement = chromosome.test_case.statements[i]
            local_search_statement = StatementLocalSearch.choose_local_search_statement(
                statement
            )

            if local_search_statement is not None:
                self._logger.debug(
                    f"Local search statement found for the statement {statement}"
                )
                local_search_statement.search(chromosome, i, objective, factory)


class TestSuiteLocalSearch(LocalSearch, ABC):

    def local_search( # noqa: D102
        self,
        chromosome: Chromosome,
        factory: TestFactory,
        objective: LocalSearchObjective | None = None,
    ) -> None:
        assert isinstance(chromosome, TestSuiteChromosome)

        self.double_branch_coverage(chromosome, LocalSearchObjective(chromosome, 0))

        for i in range(0, chromosome.test_case_chromosomes.__len__() - 1, 1):
            if LocalSearchTimer.get_instance().limit_reached():
                break

            objective = LocalSearchObjective(chromosome, i)

            # if randomness.next_float() <= config.LocalSearchConfiguration.local_search_probability: TODO: temporarily disabled for debugging purpose
            test_case_local_search = TestCaseLocalSearch()
            test_case_local_search.local_search(
                chromosome.get_test_case_chromosome(i), factory, objective
            )

    def double_branch_coverage(
        self, suite: TestSuiteChromosome, objective: LocalSearchObjective
    ) -> None:
        """Expand the test cases that each branch is at least covered twice. This
            ensures that switching through branches increases the coverage properly
            so that after mutating a statement, the previously covered branch still
            stays covered.

        Args:
            suite (TestSuiteChromosome): the test suite which should be extended.
            objective (LocalSearchObjective): the objective which delivers
                information about the fitness of the test cases.
        """
        self._logger.debug("Starting double branch coverage check")
        old_test_count = len(suite.test_case_chromosomes)
        covered_map: dict[int, int] = {}
        test_map: dict[int, TestCaseChromosome] = {}

        for test_case in suite.test_case_chromosomes:
            for (
                key,
                value,
            ) in (
                test_case.get_last_execution_result().execution_trace.executed_predicates.items()  # type: ignore[union-attr]
            ):
                covered_map[key] = covered_map.get(key, 0) + value
                test_map[key] = test_case

        duplicates: set[TestCaseChromosome] = set()

        for key, value in covered_map.items():
            if value == 1:
                clone = TestCaseChromosome(None, None, test_map[key])
                duplicates.add(clone)
                suite.add_test_case_chromosome(clone)

        self._logger.debug(
            f"Inserted {len(duplicates)} test duplicates to {old_test_count} already existing tests to have each branch covered twice"
        )
