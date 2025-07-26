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
from typing import TYPE_CHECKING

from pynguin.ga.testcasechromosome import TestCaseChromosome
from pynguin.ga.testsuitechromosome import TestSuiteChromosome
from pynguin.testcase.llmlocalsearch import LLMLocalSearch
from pynguin.testcase.localsearchobjective import LocalSearchObjective
from pynguin.testcase.localsearchstatement import StatementLocalSearch
from pynguin.testcase.localsearchtimer import LocalSearchTimer


if TYPE_CHECKING:
    from pynguin.ga.chromosome import Chromosome
    from pynguin.testcase.execution import TestCaseExecutor
    from pynguin.testcase.testfactory import TestFactory


class LocalSearch(ABC):
    """An abstract class for local search."""

    _logger = logging.getLogger(__name__)

    @abc.abstractmethod
    def local_search(
        self,
        chromosome: Chromosome,
        factory: TestFactory,
        executor: TestCaseExecutor,
        suite: TestSuiteChromosome,
        objective: LocalSearchObjective | None,
    ) -> None:
        """Executes local search on the chromosome."""


class TestCaseLocalSearch(LocalSearch, ABC):
    """Local search for a single test case."""

    def local_search(  # noqa: D102
        self,
        chromosome: Chromosome,
        factory: TestFactory,
        executor: TestCaseExecutor,
        suite: TestSuiteChromosome,
        objective: LocalSearchObjective | None,
    ) -> None:
        assert isinstance(chromosome, TestCaseChromosome)
        assert objective is not None

        for i in range(len(chromosome.test_case.statements) - 1, -1, -1):
            if LocalSearchTimer.get_instance().limit_reached():
                return

            statement = chromosome.test_case.statements[i]
            probability = 0.5
            if probability < 1:  # TODO: CHANGE PROBABILITY
                llm_local_search = LLMLocalSearch(chromosome, objective, factory, suite, executor)
                llm_local_search.llm_local_search(i)
            else:
                local_search_statement = StatementLocalSearch.choose_local_search_statement(
                    chromosome, i, objective, factory
                )
                # TODO: Change
                if local_search_statement is not None:
                    self._logger.debug(
                        "Local search statement found for the statement %s", statement
                    )
                    local_search_statement.search()


class TestSuiteLocalSearch(LocalSearch, ABC):
    """Local search for a whole test suite."""

    def local_search(  # noqa: D102
        self,
        chromosome: Chromosome,
        factory: TestFactory,
        executor: TestCaseExecutor,
        suite: TestSuiteChromosome | None = None,
        objective: LocalSearchObjective | None = None,
    ) -> None:
        assert isinstance(chromosome, TestSuiteChromosome)

        self.double_branch_coverage(chromosome, LocalSearchObjective(chromosome, 0))

        for i in range(0, len(chromosome.test_case_chromosomes), 1):
            if LocalSearchTimer.get_instance().limit_reached():
                break

            objective = LocalSearchObjective(chromosome, i)

            # if randomness.next_float() <= config.LocalSearchConfiguration.local_search_probability: TODO: temporarily disabled for debugging purpose
            test_case_local_search = TestCaseLocalSearch()
            test_case_local_search.local_search(
                chromosome.get_test_case_chromosome(i),
                factory,
                executor,
                chromosome,
                objective,
            )

    def double_branch_coverage(
        self, suite: TestSuiteChromosome, objective: LocalSearchObjective
    ) -> None:
        """Expand the test cases that each branch is at least covered twice.

        This ensures that switching through branches increases the coverage properly
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
            ) in test_case.get_last_execution_result().execution_trace.executed_predicates.items():
                covered_map[key] = covered_map.get(key, 0) + value
                test_map[key] = test_case

        duplicates: int = 0

        for key, value in covered_map.items():
            if value == 1:
                clone = TestCaseChromosome(None, None, test_map[key])
                duplicates += 1
                suite.add_test_case_chromosome(clone)

        self._logger.debug(
            "Inserted %d test duplicates to %d already existing tests to have each "
            "branch covered twice",
            duplicates,
            old_test_count,
        )
