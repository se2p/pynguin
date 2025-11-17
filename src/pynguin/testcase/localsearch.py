#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
"""Provides the local search strategies."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

import pynguin.configuration as config
import pynguin.utils.statistics.stats as stat
from pynguin.ga.testcasechromosome import TestCaseChromosome
from pynguin.testcase.llmlocalsearch import LLMLocalSearch
from pynguin.testcase.localsearchobjective import LocalSearchObjective
from pynguin.testcase.localsearchstatement import choose_local_search_statement
from pynguin.testcase.statement import (
    BooleanPrimitiveStatement,
    CollectionStatement,
    EnumPrimitiveStatement,
    PrimitiveStatement,
    Statement,
)
from pynguin.utils import randomness
from pynguin.utils.statistics.runtimevariable import RuntimeVariable

if TYPE_CHECKING:
    from pynguin.ga.testsuitechromosome import TestSuiteChromosome
    from pynguin.testcase.execution import TestCaseExecutor
    from pynguin.testcase.localsearchtimer import LocalSearchTimer
    from pynguin.testcase.testfactory import TestFactory


class TestCaseLocalSearch:
    """Local search for a single test case."""

    _logger = logging.getLogger(__name__)

    def __init__(
        self, suite: TestSuiteChromosome, executor: TestCaseExecutor, timer: LocalSearchTimer
    ) -> None:
        """Initializes the local search for a test case.

        Args:
            suite (TestSuiteChromosome): The test suite containing the test case.
            executor (TestCaseExecutor): The executor to run the test cases.
            timer (LocalSearchTimer): The timer which limits the local search run.
        """
        self._max_mutations: int = config.configuration.local_search.ls_max_different_type_mutations
        self._suite = suite
        self._executor = executor
        self._timer = timer

    def local_search(
        self,
        chromosome: TestCaseChromosome,
        factory: TestFactory,
        objective: LocalSearchObjective,
    ) -> None:
        """Executes local search on the test case.

        Args:
            chromosome (TestCaseChromosome): The test chromosome.
            factory (TestFactory): The factory to modify the test case.
            objective (LocalSearchObjective): The objective to check if improvements are made.
        """
        assert objective is not None

        # We iterate backwards because we would have to update the iterator every time when new
        # statements are added in the local search methods, which results in later statements not
        # being executed as likely as the first statement.
        # Not updating the iterator would lead to local search being applied to the same statement
        # twice.
        for i in range(len(chromosome.test_case.statements) - 1, -1, -1):
            if self._timer.limit_reached():
                return
            if (
                randomness.next_float()
                <= config.configuration.local_search.local_search_probability
                and self._check_statement_type_enabled(chromosome.test_case.statements[i])
                and i < len(chromosome.test_case.statements)
            ):
                methods: list = []
                stat.add_to_runtime_variable(RuntimeVariable.LocalSearchTotalStatements, 1)
                if config.configuration.local_search.local_search_same_datatype is True:
                    methods.append(
                        lambda pos=i: self._search_same_datatype(
                            chromosome, factory, objective, pos
                        )
                    )
                if config.configuration.local_search.local_search_different_datatype:
                    methods.append(
                        lambda pos=i: self._search_different_datatype(
                            chromosome, factory, objective, pos
                        )
                    )
                if config.configuration.local_search.local_search_llm:
                    methods.append(
                        lambda pos=i: self._search_llm(chromosome, factory, objective, pos)
                    )
                if methods:
                    result = randomness.choice(methods)()
                    if result:
                        stat.add_to_runtime_variable(
                            RuntimeVariable.LocalSearchNumberOfSuccessfulStatements, 1
                        )
                else:
                    self._logger.debug(
                        "No local search method is activated, despite general local search being "
                        "activated!"
                    )
                    return

    @staticmethod
    def _check_statement_type_enabled(statement: Statement) -> bool:
        return (
            (
                isinstance(statement, PrimitiveStatement)
                and config.configuration.local_search.local_search_primitives
            )
            or (
                isinstance(statement, CollectionStatement)
                and config.configuration.local_search.local_search_collections
            )
            or config.configuration.local_search.local_search_complex_objects
        )

    def _search_same_datatype(
        self,
        chromosome: TestCaseChromosome,
        factory: TestFactory,
        objective: LocalSearchObjective,
        position: int,
    ) -> bool:
        statement = chromosome.test_case.statements[position]
        # Randomize value because it's likely to be at a local optima
        if isinstance(statement, PrimitiveStatement) and statement.local_search_applied:
            self._logger.debug(
                "Randomizing value of statement %s at position %d since local "
                "search was already applied.",
                statement,
                position,
            )
            statement.randomize_value()

        local_search_statement = choose_local_search_statement(
            chromosome, position, objective, factory, self._timer
        )
        if local_search_statement is not None:
            self._logger.debug("Local search statement found for the statement %s", statement)
            improved = local_search_statement.search()
            statement = chromosome.test_case.statements[position]
            if isinstance(statement, PrimitiveStatement):
                statement.local_search_applied = True
            return improved
        self._logger.debug(
            "No local search statement found for the statement %s at position %d",
            statement,
            position,
        )
        return False

    def _search_different_datatype(
        self,
        chromosome: TestCaseChromosome,
        factory: TestFactory,
        objective: LocalSearchObjective,
        position: int,
    ) -> bool:
        statement = chromosome.test_case.statements[position]
        self._logger.debug(
            "Local search on different datatype for statement %s at position %d",
            statement.__class__,
            position,
        )
        old_test_case = chromosome.test_case.clone()
        last_execution_result = chromosome.get_last_execution_result()
        assert last_execution_result is not None

        counter = 0
        found = False
        while not found and counter < self._max_mutations and not self._timer.limit_reached():
            old_size = len(chromosome.test_case.statements)
            if factory.change_statement_type(chromosome, position) and objective.has_improved(
                chromosome
            ):
                self._logger.debug("Local search has found another possible datatype")
                found = True
                position += len(chromosome.test_case.statements) - old_size
            else:
                chromosome.test_case = old_test_case.clone()
                chromosome.set_last_execution_result(last_execution_result)
            counter += 1

        if not found:
            self._logger.debug("Local search did not find another possible datatype.")
        else:
            self._search_same_datatype(chromosome, factory, objective, position)
        return found

    def _search_llm(
        self,
        chromosome: TestCaseChromosome,
        factory: TestFactory,
        objective: LocalSearchObjective,
        position: int,
    ) -> bool:
        statement = chromosome.test_case.statements[position]
        # Not querying LLM for boolean or enum primitives since this is too expensive to query
        # for llm requests
        if isinstance(statement, BooleanPrimitiveStatement | EnumPrimitiveStatement):
            self._logger.debug(
                "Skipping LLM local search for statement %s at position %d since it's a "
                "boolean or enum primitive. Instead use same datatype local search.",
                statement,
                position,
            )
            return self._search_same_datatype(chromosome, factory, objective, position)
        return LLMLocalSearch(
            chromosome, objective, factory, self._suite, self._executor
        ).llm_local_search(position)


class TestSuiteLocalSearch:
    """Local search for a whole test suite."""

    _logger = logging.getLogger(__name__)

    def local_search(
        self,
        chromosome: TestSuiteChromosome,
        factory: TestFactory,
        executor: TestCaseExecutor,
        timer: LocalSearchTimer,
    ) -> None:
        """Executes local search on the suite.

        Args:
            chromosome (Chromosome): The test suite chromosome to be modified.
            factory (TestFactory): The factory to modify the test cases.
            executor (TestCaseExecutor): The executor to run the test cases.
            timer (LocalSearchTimer): The timer to manage the local search budget.
        """
        start_time = int(time.perf_counter()) * 1000
        stat.add_to_runtime_variable(RuntimeVariable.TotalLocalSearchIterations, 1)
        self.double_branch_coverage(chromosome)

        indices = list(range(len(chromosome.test_case_chromosomes)))
        randomness.shuffle(indices)
        test_case_local_search = TestCaseLocalSearch(chromosome, executor, timer)
        for i in indices:
            if timer.limit_reached():
                break
            objective = LocalSearchObjective(chromosome, i)
            test_case_local_search.local_search(
                chromosome.get_test_case_chromosome(i),
                factory,
                objective,
            )
        time_dif = int(time.perf_counter()) * 1000 - start_time
        stat.add_to_runtime_variable(RuntimeVariable.TotalLocalSearchTime, time_dif)

    def double_branch_coverage(self, suite: TestSuiteChromosome) -> None:
        """Expand the test cases that each branch is at least covered twice.

        This ensures that switching through branches increases the coverage properly
        so that after mutating a statement, the previously covered branch still
        stays covered. This is similar to Evosuite.

        Args:
            suite (TestSuiteChromosome): the test suite which should be extended.
        """
        self._logger.debug("Starting double branch coverage check")
        old_test_count = len(suite.test_case_chromosomes)
        covered_map: dict[int, int] = {}
        test_map: dict[int, TestCaseChromosome] = {}

        for test_case in suite.test_case_chromosomes:
            execution_result = test_case.get_last_execution_result()
            assert execution_result is not None
            for (
                key,
                value,
            ) in execution_result.execution_trace.executed_predicates.items():
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
