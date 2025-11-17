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
from pynguin.large_language_model.llmagent import (
    LLMAgent,
    get_module_source_code,
    get_part_of_source_code,
    shorten_line_annotations,
)
from pynguin.large_language_model.parsing.helpers import unparse_test_case
from pynguin.testcase.execution import TestCaseExecutor
from pynguin.testcase.localsearchobjective import LocalSearchObjective
from pynguin.testcase.statement import (
    CollectionStatement,
    ConstructorStatement,
    FunctionStatement,
    MethodStatement,
    Statement,
    VariableCreatingStatement,
)
from pynguin.testcase.testfactory import TestFactory
from pynguin.utils.generic.genericaccessibleobject import (
    GenericConstructor,
    GenericFunction,
    GenericMethod,
)
from pynguin.utils.report import LineAnnotation, get_coverage_report
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

    def llm_local_search(self, position) -> bool:
        """Starts local search using LLMs for the statement at the position.

        Args:
            position (int): The position of the statement in the test case.

        Returns:
            True if the local search improved the test case, False otherwise.
        """
        old_chromosomes = self.suite.test_case_chromosomes.copy()
        failing_test = self.chromosome.is_failing()
        agent = LLMAgent()

        setup_result = self._setup_llm_call(position)
        if setup_result is None:
            self._logger.debug("Skipping LLM local search call, because the setup failed.")
            return False
        unparsed_test_case, module_source_code, line_annotations = setup_result
        output = agent.local_search_call(
            position=position,
            test_case_source_code=unparsed_test_case,
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
            return False

        if self.objective.has_improved(test_case):
            self._logger.debug("The llm request has improved the fitness of the test case")
            self.chromosome = test_case
            if not failing_test:
                stat.add_to_runtime_variable(RuntimeVariable.TotalLocalSearchLLMSuccessCalls, 1)
            else:
                stat.add_to_runtime_variable(
                    RuntimeVariable.TotalLocalSearchLLMSuccessCallsDespiteFailing, 1
                )
            return True

        self.suite.test_case_chromosomes = old_chromosomes
        self._logger.debug(
            "The llm request hasn't improved the fitness of the test case, "
            "reverting to the old test case"
        )
        return False

    def _setup_llm_call(self, position: int) -> tuple[str, str, list[LineAnnotation]] | None:
        failing_test = self.chromosome.is_failing()
        self._logger.debug("Starting local search with LLMs at position %d", position)
        metrics = set(config.configuration.statistics_output.coverage_metrics)
        report = get_coverage_report(self.suite, self.executor.subject_properties, metrics)

        stat.add_to_runtime_variable(RuntimeVariable.TotalLocalSearchLLMCalls, 1)
        if failing_test:
            stat.add_to_runtime_variable(RuntimeVariable.TotalLocalSearchLLMCallsFailingTests, 1)
        if config.configuration.local_search.ls_llm_whole_module:
            module_source_code = get_module_source_code()
            line_annotations = report.line_annotations
        else:
            statement = self.chromosome.test_case.statements[position]
            if not isinstance(statement, VariableCreatingStatement):
                self._logger.debug(
                    "Statement is not VariableCreatingStatement, skipping LLM request."
                )
                return None
            module_source_code, line_annotations = self.get_shortened_source_code(
                statement, report.line_annotations
            )
        if len(module_source_code) == 0 or len(line_annotations) == 0:
            self._logger.debug(
                "This statement is not used in any method of source code, "
                "or all branches are covered, skipping LLM request."
            )
            stat.add_to_runtime_variable(RuntimeVariable.TotalLocalSearchSkippedLLMCalls, 1)
            return None
        unparsed_test_case = unparse_test_case(self.chromosome.test_case)
        if unparsed_test_case is None:
            self._logger.debug("Failed to unparse test case, skipping LLM request.")
            return None
        return unparsed_test_case, module_source_code, line_annotations

    def get_shortened_source_code(
        self, statement: VariableCreatingStatement, line_annotations: list[LineAnnotation]
    ) -> tuple[str, list[LineAnnotation]]:
        """Returns the shortened source code of the module under test and shortens line annotations.

        Everything of the source code, that is not forward dependent on the given statement
        (including this statement) is removed. The list of LineAnnotations is also shortened to
        only include the lines of the remaining source code. The line numerations of the original
        code are added to the source code to match to the corresponding line annotation.

        Args:
            statement: The statement for which the source code should be shortened.
            line_annotations (list[LineAnnotation]): The line annotations of the whole module.

        Returns:
            str: The source code of the current test case.
            list[LineAnnotation]: The line annotations of the current test case.
        """
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
            name = self._get_name(stmt)
            if name is not None and len(name) > 0:
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

    def _get_name(self, stmt: Statement) -> str | None:
        name = ""
        accessible = stmt.accessible_object()
        self._logger.debug("Retrieving name for accessible object of type %s", type(accessible))

        if isinstance(accessible, GenericMethod):
            name = f"{accessible.owner.full_name.split('.', 1)[1]}.{accessible.method_name}"
        elif isinstance(accessible, GenericFunction):
            if accessible.function_name is None:
                self._logger.debug("Skipping function with no name for name retrieval")
                return None
            name = accessible.function_name
        elif isinstance(accessible, GenericConstructor):
            if accessible.owner is None:
                self._logger.debug("Skipping constructor with no owner for name retrieval")
                return None
            name = accessible.owner.full_name.split(".", 1)[1] + ".__init__"
        elif accessible is None and isinstance(stmt, CollectionStatement):
            self._logger.debug("Skipping collection statement for name retrieval")
            # Collections do not have an accessible object in cases like this: var_1 = [var2]
            return None
        else:
            self._logger.debug("Unknown accessible object type")
        return name
