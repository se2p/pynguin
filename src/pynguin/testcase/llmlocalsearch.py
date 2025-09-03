#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT

"""Gives access to local search with LLMs."""

import logging

import pynguin.configuration as config
import pynguin.utils.statistics.stats as stat

from pynguin.ga.testcasechromosome import TestCaseChromosome
from pynguin.ga.testsuitechromosome import TestSuiteChromosome
from pynguin.large_language_model.llmagent import LLMAgent
from pynguin.large_language_model.parsing.helpers import unparse_test_case
from pynguin.testcase.execution import TestCaseExecutor
from pynguin.testcase.localsearchobjective import LocalSearchObjective
from pynguin.testcase.testfactory import TestFactory
from pynguin.utils.report import get_coverage_report
from pynguin.utils.statistics.runtimevariable import RuntimeVariable


class LLMLocalSearch:
    """Provides access to local search using LLMs."""

    _logger = logging.getLogger(__name__)

    def __init__(
        self,
        chromosome: TestCaseChromosome,
        objective: LocalSearchObjective,
        factory: TestFactory,
        suite: TestSuiteChromosome,
        executor: TestCaseExecutor,
    ):
        """Initializes the class.

        Args:
            chromosome (TestCaseChromosome): The test case which should be changed.
            objective (LocalSearchObjective): The objective which checks if improvements are made.
            factory (TestFactory): The test factory which creates the test case.
            suite (TestSuiteChromosome): The whole test suite.
            executor (TestCaseExecutor): The test executor.
        """
        self.chromosome = chromosome
        self.objective = objective
        self.factory = factory
        self.suite = suite
        self.executor = executor

    def llm_local_search(self, position):
        """Starts local search using LLMs for the statement at the position.

        Args:
            position (int): The position of the statement in the test case.
        """
        failing_test = self.chromosome.is_failing()
        self._logger.debug("Starting local search with LLMs at position %d", position)
        metrics = {config.CoverageMetric.BRANCH, config.CoverageMetric.LINE}
        report = get_coverage_report(self.suite, self.executor, metrics)
        agent = LLMAgent()
        stat.add_to_runtime_variable(RuntimeVariable.TotalLocalSearchLLMCalls, 1)
        if failing_test:
            stat.add_to_runtime_variable(RuntimeVariable.TotalLocalSearchLLMCallsFailingTests, 1)
        output = agent.local_search_call(
            position=position,
            test_case_source_code=unparse_test_case(self.chromosome.test_case),
            branch_coverage=report.line_annotations,
        )
        self._logger.debug(output)

        test_cases = agent.llm_test_case_handler.get_test_case_chromosomes_from_llm_results(
            output,
            self.chromosome.test_case.test_cluster,
            self.factory,
            self.chromosome.get_fitness_functions(),
            self.chromosome.get_coverage_functions(),
        )

        if len(test_cases) == 1:
            test_case = test_cases[0]
        else:
            self._logger.debug("Wrong number of testcases parsed, only needed one")
            return

        if self.objective.has_improved(test_case):
            self._logger.debug("The llm request has improved the fitness of the test case")
            self.chromosome = test_case
            if not failing_test:
                stat.add_to_runtime_variable(RuntimeVariable.TotalLocalSearchLLMSuccessCalls, 1)
            else:
                stat.add_to_runtime_variable(
                    RuntimeVariable.TotalLocalSearchLLMSuccessCallsDespiteFailing, 1
                )

        else:
            self._logger.debug(
                "The llm request hasn't improved the fitness of the test case, "
                "reverting to the old test case"
            )
