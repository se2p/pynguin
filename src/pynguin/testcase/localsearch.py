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

import pynguin.configuration as config

from pynguin.ga.testcasechromosome import TestCaseChromosome
from pynguin.ga.testsuitechromosome import TestSuiteChromosome
from pynguin.testcase.localsearchobjective import LocalSearchObjective
from pynguin.testcase.localsearchstatement import StatementLocalSearch
from pynguin.testcase.localsearchtimer import LocalSearchTimer
from pynguin.testcase.statement import PrimitiveStatement
from pynguin.testcase.variablereference import VariableReference
from pynguin.utils import randomness


if TYPE_CHECKING:
    from pynguin.ga.chromosome import Chromosome
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
    """Local search for a single test case."""

    def local_search(  # noqa: D102
        self,
        chromosome: TestCaseChromosome,
        factory: TestFactory,
        objective: LocalSearchObjective | None,
    ) -> None:
        assert objective is not None

        for i in range(len(chromosome.test_case.statements) - 1, -1, -1):
            if LocalSearchTimer.get_instance().limit_reached():
                return
            methods: list = []
            if config.LocalSearchConfiguration.local_search_same_datatype:
                methods.append(
                    lambda: self._search_same_datatype(chromosome, factory, objective, i)
                )
            if config.LocalSearchConfiguration.local_search_other_datatype:
                methods.append(
                    lambda: self._search_other_datatype(chromosome, factory, objective, i)
                )
            if config.LocalSearchConfiguration.local_search_llm:
                methods.append(self._search_llm())
            if methods:
                randomness.choice(methods)()

    def _search_same_datatype(
        self,
        chromosome: TestCaseChromosome,
        factory: TestFactory,
        objective: LocalSearchObjective,
        position,
    ):
        statement = chromosome.test_case.statements[position]
        #Randomize value because it's likely to be at a local optima
        if isinstance(statement, PrimitiveStatement) and statement.local_search_applied:
            statement.randomize_value()

        local_search_statement = StatementLocalSearch.choose_local_search_statement(
            chromosome, position, objective, factory
        )
        # TODO: Change
        if local_search_statement is not None:
            self._logger.debug("Local search statement found for the statement %s", statement)
            local_search_statement.search()
            statement = chromosome.test_case.statements[position]
            if isinstance(statement, PrimitiveStatement):
                statement.local_search_applied = True

    def _search_other_datatype(
        self,
        chromosome: TestCaseChromosome,
        factory: TestFactory,
        objective: LocalSearchObjective,
        position,
    ) -> None:
        statement = chromosome.test_case.statements[position]
        memo: dict[VariableReference, VariableReference] = {}
        old_statement = statement.clone(chromosome.test_case, memo)
        last_execution_result = chromosome.get_last_execution_result()

        counter = 0
        found = False
        while (
            not found
            and counter < config.LocalSearchConfiguration.max_other_type_mutation
            and not LocalSearchTimer.get_instance().limit_reached()
        ):
            # TODO: Search other type

            if objective.has_improved(chromosome):
                self._logger.debug("Local search has found another possible datatype")
                found = True
            counter += 1

        if not found:
            self._logger.debug(
                "Local search did not find another possible datatype, reverting to old one"
            )
            chromosome.test_case.statements[position] = old_statement
            chromosome.set_last_execution_result(last_execution_result)
        else:
            self._search_same_datatype(chromosome, factory, objective, position)

    def _search_llm(self):
        # TODO: Implement me!
        pass


class TestSuiteLocalSearch(LocalSearch, ABC):
    """Local search for a whole test suite."""

    def local_search(  # noqa: D102
        self,
        chromosome: Chromosome,
        factory: TestFactory,
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
                chromosome.get_test_case_chromosome(i), factory, objective
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
            ) in (
                test_case.get_last_execution_result().execution_trace.executed_predicates.items()  # type: ignore[union-attr]
            ):
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
