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
from pynguin.large_language_model.llmagent import get_module_source_code
from pynguin.large_language_model.llmagent import get_part_of_source_code
from pynguin.large_language_model.llmagent import shorten_line_annotations
from pynguin.large_language_model.parsing.helpers import unparse_test_case
from pynguin.testcase.execution import TestCaseExecutor
from pynguin.testcase.localsearchobjective import LocalSearchObjective
from pynguin.testcase.statement import CollectionStatement
from pynguin.testcase.statement import ConstructorStatement
from pynguin.testcase.statement import FunctionStatement
from pynguin.testcase.statement import MethodStatement
from pynguin.testcase.statement import VariableCreatingStatement
from pynguin.testcase.testfactory import TestFactory
from pynguin.utils.generic.genericaccessibleobject import GenericConstructor
from pynguin.utils.generic.genericaccessibleobject import GenericFunction
from pynguin.utils.generic.genericaccessibleobject import GenericMethod
from pynguin.utils.report import LineAnnotation
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
        if config.configuration.local_search.llm_whole_module:
            module_source_code = get_module_source_code()
            line_annotations = report.line_annotations
        else:
            module_source_code, line_annotations = self.get_shortened_source_code(
                position, report.line_annotations
            )
        if len(module_source_code) == 0 or len(line_annotations) == 0:
            self._logger.debug(
                "This statement is not used in any method of source code, "
                "or all branches are covered, skipping LLM request."
            )
            stat.add_to_runtime_variable(RuntimeVariable.TotalLocalSearchSkippedLLMCalls, 1)
            return
        output = agent.local_search_call(
            position=position,
            test_case_source_code=unparse_test_case(self.chromosome.test_case),
            branch_coverage=line_annotations,
            module_source_code=module_source_code,
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

    def get_shortened_source_code(
        self, position: int, line_annotations: list[LineAnnotation]
    ) -> (str, list[LineAnnotation]):
        """Returns the shortened source code of the module under test and shortens line annotations.

        Only the methods where this statement is used are kept.

        Returns:
            str: The source code of the current test case.
            list[LineAnnotation]: The line annotations of the current test case.
        """
        statement = self.chromosome.test_case.statements[position]
        assert isinstance(statement, VariableCreatingStatement)
        dependencies = self.chromosome.test_case.get_forward_dependencies(statement.ret_val)
        if isinstance(statement, MethodStatement | FunctionStatement | ConstructorStatement):
            dependencies.add(statement.ret_val)
        statements = [
            statement
            for statement in self.chromosome.test_case.statements
            if statement.ret_val in dependencies
        ]
        out = ""
        self._logger.debug("statements: %s", len(statements))
        shortened: list[LineAnnotation] = []
        for stmt in statements:
            name = ""
            accessible = stmt.accessible_object()
            if isinstance(accessible, GenericMethod):
                name = f"{accessible.owner.full_name.split('.', 1)[1]}.{accessible.method_name}"
            elif isinstance(accessible, GenericFunction):
                name = accessible.function_name
            elif isinstance(accessible, GenericConstructor):
                name = accessible.owner.full_name.split(".", 1)[1] + ".__init__"
            elif accessible is None and isinstance(stmt, CollectionStatement):
                # Collections do not have an accessible object in cases like this: var_1 = [var2]
                continue
            else:
                # TODO: handle fields / enums
                self._logger.debug("Unknown accessible object type")
            if len(name) > 0:
                module_source = get_part_of_source_code(name)
                if type(module_source) is str:
                    out += module_source + "\n\n"
                    shortened.extend(shorten_line_annotations(line_annotations, name))
                else:
                    self._logger.debug(
                        "Could not find source code for %s, wrong type %s",
                        name,
                        type(module_source),
                    )
        self._logger.debug(out)
        return out, shortened
