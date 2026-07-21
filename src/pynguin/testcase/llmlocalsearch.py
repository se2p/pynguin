#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
"""Provides LLM-based local search for the libcst test-case representation.

:meth:`LLMLocalSearch.llm_local_search` performs one round trip for a single
statement: it serializes the test case, shortens the LLM context to the
statement's forward dependencies, queries the LLM, deserializes the reply with
:class:`pynguin.large_language_model.parsing.deserializer.CstStatementDeserializer`
(via :class:`~pynguin.large_language_model.llmtestcasehandler.LLMTestCaseHandler`),
and keeps the mutated test case only if it improves the objective. It is wired up
by :mod:`pynguin.testcase.localsearch` and gated behind ``local_search_llm``, which
stays default-off (see ``configuration.py``), so classic local search does not
depend on it.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pynguin.configuration as config
import pynguin.utils.statistics.stats as stat
from pynguin.large_language_model.llmagent import (
    LLMAgent,
    get_module_source_code,
    get_part_of_source_code,
    shorten_line_annotations,
)
from pynguin.utils.generic.genericaccessibleobject import (
    GenericConstructor,
    GenericFunction,
    GenericMethod,
)
from pynguin.utils.report import get_coverage_report
from pynguin.utils.statistics.runtimevariable import RuntimeVariable

if TYPE_CHECKING:
    from pynguin.ga.testcasechromosome import TestCaseChromosome
    from pynguin.ga.testsuitechromosome import TestSuiteChromosome
    from pynguin.testcase.execution import TestCaseExecutor
    from pynguin.testcase.localsearchobjective import LocalSearchObjective
    from pynguin.testcase.testcase import Statement
    from pynguin.testcase.testfactory import TestFactory
    from pynguin.utils.report import LineAnnotation


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
    ) -> None:
        """Initializes the LLM local search hook.

        Args:
            chromosome: The test case chromosome to search.
            objective: The objective to check if improvements are made.
            factory: The factory to modify the test case.
            suite: The test suite containing the test case.
            executor: The executor to run the test cases.
        """
        self._chromosome = chromosome
        self._objective = objective
        self._factory = factory
        self._suite = suite
        self._executor = executor

    def llm_local_search(self, position: int) -> bool:
        """Runs one LLM local-search round trip on the statement at ``position``.

        Args:
            position: The index of the statement to search.

        Returns:
            ``True`` if the LLM mutation improved the test case, ``False`` otherwise.
        """
        old_chromosomes = list(self._suite.test_case_chromosomes)
        failing_test = self._chromosome.is_failing()
        agent = LLMAgent()

        setup_result = self._setup_llm_call(position)
        if setup_result is None:
            self._logger.debug("Skipping LLM local search call, because the setup failed.")
            return False
        test_case_source_code, module_source_code, line_annotations = setup_result

        output = agent.local_search_call(
            position=position,
            test_case_source_code=test_case_source_code,
            branch_coverage=line_annotations,
            module_source_code=module_source_code,
        )
        self._logger.debug("LLM local search response: %s", output)

        test_cases = agent.llm_test_case_handler.get_test_case_chromosomes_from_llm_results(
            llm_query_results=output,
            test_cluster=self._factory.test_cluster,
            test_factory=self._factory,
            fitness_functions=self._chromosome.get_fitness_functions(),
            coverage_functions=self._chromosome.get_coverage_functions(),
        )
        if len(test_cases) != 1:
            self._logger.debug(
                "Expected exactly one parsed test case from the LLM, got %d.", len(test_cases)
            )
            return False
        candidate = test_cases[0]

        if self._objective.has_improved(candidate):
            self._logger.debug("The LLM request improved the fitness of the test case.")
            if failing_test:
                stat.add_to_runtime_variable(
                    RuntimeVariable.TotalLocalSearchLLMSuccessCallsDespiteFailing, 1
                )
            else:
                stat.add_to_runtime_variable(RuntimeVariable.TotalLocalSearchLLMSuccessCalls, 1)
            return True

        self._suite.test_case_chromosomes = old_chromosomes
        self._logger.debug(
            "The LLM request did not improve the fitness of the test case, "
            "reverting to the old test case."
        )
        return False

    def _setup_llm_call(self, position: int) -> tuple[str, str, list[LineAnnotation]] | None:
        """Assembles the prompt inputs for the LLM call at ``position``.

        Args:
            position: The index of the statement to search.

        Returns:
            A ``(test_case_source, module_source, line_annotations)`` tuple, or
            ``None`` if the call should be skipped.
        """
        failing_test = self._chromosome.is_failing()
        self._logger.debug("Starting local search with LLMs at position %d", position)
        metrics = set(config.configuration.statistics_output.coverage_metrics)
        report = get_coverage_report(self._suite, self._executor.subject_properties, metrics)

        stat.add_to_runtime_variable(RuntimeVariable.TotalLocalSearchLLMCalls, 1)
        if failing_test:
            stat.add_to_runtime_variable(RuntimeVariable.TotalLocalSearchLLMCallsFailingTests, 1)

        if config.configuration.local_search.ls_llm_whole_module:
            module_source_code = get_module_source_code()
            line_annotations = report.line_annotations
        else:
            statement = self._chromosome.test_case.get_statement(position)
            if statement.bound_variable is None:
                self._logger.debug(
                    "Statement at position %d binds no variable, skipping LLM request.", position
                )
                return None
            module_source_code, line_annotations = self.get_shortened_source_code(
                position, report.line_annotations
            )

        if len(module_source_code) == 0 or len(line_annotations) == 0:
            self._logger.debug(
                "This statement is not used in any method of the source code, "
                "or all branches are covered, skipping LLM request."
            )
            stat.add_to_runtime_variable(RuntimeVariable.TotalLocalSearchSkippedLLMCalls, 1)
            return None

        test_case_source_code = self._chromosome.test_case.to_test_function().code
        if not test_case_source_code:
            self._logger.debug("Failed to serialize test case, skipping LLM request.")
            return None
        return test_case_source_code, module_source_code, line_annotations

    def get_shortened_source_code(
        self, position: int, line_annotations: list[LineAnnotation]
    ) -> tuple[str, list[LineAnnotation]]:
        """Shortens the module source to the forward dependencies of a statement.

        Everything in the source code that the statement at ``position`` is not
        forward-dependent on (the statement itself and every later statement
        transitively reading a variable it binds) is dropped. The line annotations
        are shortened accordingly. Original line numbers are kept so the annotations
        still line up with the returned source.

        Args:
            position: The index of the statement whose dependencies define the scope.
            line_annotations: The line annotations of the whole module.

        Returns:
            The shortened module source code and the matching line annotations.
        """
        dependency_indices = self._chromosome.test_case.forward_dependencies(position)
        statements = [
            self._chromosome.test_case.get_statement(index) for index in sorted(dependency_indices)
        ]
        out = ""
        shortened: list[LineAnnotation] = []
        for stmt in statements:
            name = self._get_name(stmt)
            if name:
                module_source = get_part_of_source_code(name)
                if module_source:
                    out += module_source + "\n\n"
                    shortened.extend(shorten_line_annotations(line_annotations, name))
                else:
                    self._logger.debug("Could not find source code for %s.", name)
        self._logger.debug("Shortened source code:\n%s", out)
        return out, shortened

    def _get_name(self, stmt: Statement) -> str | None:
        """Returns the dotted SUT name called by ``stmt``, or ``None``.

        Args:
            stmt: The statement to inspect.

        Returns:
            The name of the function, method or constructor invoked by the
            statement, relative to the module, or ``None`` if it does not call a
            named accessible object.
        """
        accessible = stmt.accessible
        if isinstance(accessible, GenericMethod):
            return f"{accessible.owner.full_name.split('.', 1)[1]}.{accessible.method_name}"
        if isinstance(accessible, GenericFunction):
            if accessible.function_name is None:
                self._logger.debug("Skipping function with no name for name retrieval.")
                return None
            return accessible.function_name
        if isinstance(accessible, GenericConstructor):
            if accessible.owner is None:
                self._logger.debug("Skipping constructor with no owner for name retrieval.")
                return None
            return accessible.owner.full_name.split(".", 1)[1] + ".__init__"
        self._logger.debug("No named accessible object for statement, skipping.")
        return None
