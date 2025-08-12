#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
"""Provides the local search strategies."""

from __future__ import annotations

import logging

from typing import TYPE_CHECKING

import pynguin.configuration as config
import pynguin.utils.statistics.stats as stat

from pynguin.ga.testcasechromosome import TestCaseChromosome
from pynguin.ga.testsuitechromosome import TestSuiteChromosome
from pynguin.testcase.llmlocalsearch import LLMLocalSearch
from pynguin.testcase.localsearchobjective import LocalSearchObjective
from pynguin.testcase.localsearchstatement import choose_local_search_statement
from pynguin.testcase.localsearchtimer import LocalSearchTimer
from pynguin.testcase.statement import ConstructorStatement
from pynguin.testcase.statement import FieldStatement
from pynguin.testcase.statement import FunctionStatement
from pynguin.testcase.statement import MethodStatement
from pynguin.testcase.statement import PrimitiveStatement
from pynguin.utils import randomness
from pynguin.utils.statistics.runtimevariable import RuntimeVariable


if TYPE_CHECKING:
    from pynguin.ga.chromosome import Chromosome
    from pynguin.testcase.execution import TestCaseExecutor
    from pynguin.testcase.testfactory import TestFactory


class TestCaseLocalSearch:
    """Local search for a single test case."""

    _logger = logging.getLogger(__name__)

    def __init__(
        self, total_statements: int, suite: TestSuiteChromosome, executor: TestCaseExecutor
    ) -> None:
        """Initializes the local search for a test case.

        Args:
            total_statements (int): The total number of statements in the test case.
            suite (TestSuiteChromosome): The test suite containing the test case.
            executor (TestCaseExecutor): The executor to run the test cases.
        """
        assert total_statements > 0, "Total statements must be greater than zero."
        self._max_mutations: int = (
            int(
                config.configuration.local_search.max_other_type_mutation
                * config.configuration.local_search.local_search_time
            )
            // total_statements
        )
        self._suite = suite
        self._executor = executor

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

        for i in range(len(chromosome.test_case.statements) - 1, -1, -1):
            if LocalSearchTimer.get_instance().limit_reached():
                return
            if (
                randomness.next_float()
                <= config.configuration.local_search.local_search_probability
                and (
                    config.configuration.local_search.enable_complex_objects_local_search
                    or not isinstance(
                        chromosome.test_case.statements[i],
                        FieldStatement | MethodStatement | FunctionStatement | ConstructorStatement,
                    )
                )
            ):
                methods: list = []
                old_stat = stat.output_variables.get(
                    RuntimeVariable.LocalSearchTotalStatements.name
                )
                stat.set_output_variable_for_runtime_variable(
                    RuntimeVariable.LocalSearchTotalStatements,
                    old_stat.value + 1 if old_stat is not None else 0,
                )
                if config.configuration.local_search.local_search_same_datatype is True:
                    methods.append(
                        lambda pos=i: self._search_same_datatype(
                            chromosome, factory, objective, pos
                        )
                    )
                if config.configuration.local_search.local_search_other_datatype:
                    methods.append(
                        lambda pos=i: self._search_other_datatype(
                            chromosome, factory, objective, pos
                        )
                    )
                if config.configuration.local_search.local_search_llm:
                    methods.append(
                        lambda pos=i: LLMLocalSearch(
                            chromosome, objective, factory, self._suite, self._executor
                        ).llm_local_search(pos)
                    )
                if methods:
                    randomness.choice(methods)()
                else:
                    self._logger.debug(
                        "No local search method is activated, despite general local search being "
                        "activated!"
                    )
                    return

    def _search_same_datatype(
        self,
        chromosome: TestCaseChromosome,
        factory: TestFactory,
        objective: LocalSearchObjective,
        position,
    ):
        statement = chromosome.test_case.statements[position]
        # Randomize value because it's likely to be at a local optima
        if isinstance(statement, PrimitiveStatement) and statement.local_search_applied:
            statement.randomize_value()

        local_search_statement = choose_local_search_statement(
            chromosome, position, objective, factory
        )
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
        self._logger.debug(
            "Local search on other datatype for statement %s at position %d",
            statement.__class__,
            position,
        )
        old_test_case = chromosome.test_case.clone()
        last_execution_result = chromosome.get_last_execution_result()

        counter = 0
        found = False
        while (
            not found
            and counter < self._max_mutations
            and not LocalSearchTimer.get_instance().limit_reached()
        ):
            if factory.change_statement(chromosome, position) and objective.has_improved(
                chromosome
            ):
                self._logger.debug("Local search has found another possible datatype")
                found = True
            else:
                chromosome.test_case = old_test_case.clone()
                chromosome.set_last_execution_result(last_execution_result)
            counter += 1

        if not found:
            self._logger.debug("Local search did not find another possible datatype.")
        else:
            self._search_same_datatype(chromosome, factory, objective, position)


class TestSuiteLocalSearch:
    """Local search for a whole test suite."""

    _logger = logging.getLogger(__name__)

    def local_search(
        self,
        chromosome: Chromosome,
        factory: TestFactory,
        executor: TestCaseExecutor,
    ) -> None:
        """Executes local search on the suite.

        Args:
            chromosome (Chromosome): The test suite chromosome to be modified.
            factory (TestFactory): The factory to modify the test cases.
            executor (TestCaseExecutor): The executor to run the test cases.
        """
        assert isinstance(chromosome, TestSuiteChromosome)

        self.double_branch_coverage(chromosome)

        total_statements = sum(
            len(test_case.statements) for test_case in chromosome.test_case_chromosomes
        )

        indices = list(range(len(chromosome.test_case_chromosomes)))
        randomness.shuffle(indices)
        test_case_local_search = TestCaseLocalSearch(total_statements, chromosome, executor)
        for i in indices:
            if LocalSearchTimer.get_instance().limit_reached():
                return
            objective = LocalSearchObjective(chromosome, i)
            test_case_local_search.local_search(
                chromosome.get_test_case_chromosome(i),
                factory,
                objective,
            )

    def double_branch_coverage(self, suite: TestSuiteChromosome) -> None:
        """Expand the test cases that each branch is at least covered twice.

        This ensures that switching through branches increases the coverage properly
        so that after mutating a statement, the previously covered branch still
        stays covered.

        Args:
            suite (TestSuiteChromosome): the test suite which should be extended.
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
