#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides an assertion generator"""
from __future__ import annotations

import logging
from collections import Counter
from typing import TYPE_CHECKING

from ordered_set import OrderedSet

import pynguin.assertion.assertion as ass
import pynguin.assertion.assertiontraceobserver as ato
import pynguin.assertion.mutation_analysis.mutationadapter as ma
import pynguin.configuration as config
import pynguin.ga.chromosomevisitor as cv
from pynguin.utils import randomness

if TYPE_CHECKING:
    import pynguin.ga.testcasechromosome as tcc
    import pynguin.ga.testsuitechromosome as tsc
    import pynguin.testcase.execution as ex
    import pynguin.testcase.statement as st
    import pynguin.testcase.testcase as tc


class AssertionGenerator(cv.ChromosomeVisitor):
    """A simple assertion generator.
    Creates all regression assertions."""

    _logger = logging.getLogger(__name__)

    def __init__(self, executor: ex.TestCaseExecutor, base_executions: int = 2):
        """
        Create new assertion generator.

        Args:
            executor: the executor that will be used to execute the test cases.
            base_executions: How often should the tests be executed to filter
                out trivially flaky assertions, e.g., str representations based on
                memory locations.
        """
        self._base_executions = base_executions
        self._executor = executor
        self._executor.add_observer(ato.AssertionTraceObserver())

    def visit_test_suite_chromosome(self, chromosome: tsc.TestSuiteChromosome) -> None:
        self._generate_assertions(
            [chrom.test_case for chrom in chromosome.test_case_chromosomes]
        )

    def visit_test_case_chromosome(self, chromosome: tcc.TestCaseChromosome) -> None:
        self._generate_assertions([chromosome.test_case])

    def _generate_assertions(self, test_cases: list[tc.TestCase]) -> None:
        """Adds assertions to the given test case.

        Args:
            test_cases: the test case for which assertions should be generated.
        """
        self._add_assertions(self._execute(test_cases))

    def _execute(
        self, test_cases: list[tc.TestCase]
    ) -> list[tuple[tc.TestCase, list[ex.ExecutionResult]]]:
        tests_and_results: list[tuple[tc.TestCase, list[ex.ExecutionResult]]] = [
            (test_case, []) for test_case in test_cases
        ]
        for _ in range(self._base_executions):
            randomness.RNG.shuffle(tests_and_results)
            for test, results in tests_and_results:
                results.append(self._executor.execute(test))
        return tests_and_results

    def _add_assertions(
        self, tests_and_results: list[tuple[tc.TestCase, list[ex.ExecutionResult]]]
    ):
        for test_case, results in tests_and_results:
            self._add_assertions_for(test_case, results)

    def _add_assertions_for(
        self, test_case: tc.TestCase, results: list[ex.ExecutionResult]
    ):
        # In order to avoid repeating the same assertions after each statement,
        # we keep track of the last assertions and only assert things, if they
        # have changed.
        previous_statement_assertions: OrderedSet[ass.Assertion] = OrderedSet()
        for statement in test_case.statements:
            current_statement_assertions = self._get_assertions_for(results, statement)
            for assertion in current_statement_assertions:
                if (
                    not config.configuration.test_case_output.allow_stale_assertions
                    and assertion in previous_statement_assertions
                ):
                    # We already saw the same assertion in the previous statement
                    # So the value did not change.
                    continue
                if (
                    test_case.size_with_assertions()
                    >= config.configuration.test_case_output.max_length_test_case
                ):
                    self._logger.debug(
                        "No more assertions are added, because the maximum length "
                        "of a test case with its assertions was reached"
                    )
                    return
                statement.add_assertion(assertion)

            # Only update the previously seen assertions when we encounter a
            # statement that actually affects assertions.
            if statement.affects_assertions:
                previous_statement_assertions = current_statement_assertions

    def _get_assertions_for(  # pylint:disable=no-self-use
        self, results: list[ex.ExecutionResult], statement: st.Statement
    ) -> OrderedSet[ass.Assertion]:
        """Returns the set of assertions for the given statement.

        Args:
            results: The results from which we want to extract the assertions.
            statement: The statement after which the assertions hold.

        Returns:
            An ordered set of assertions for the given statement.
        """
        assert len(results) > 0, "Requires at least one result."
        assertions: list[OrderedSet[ass.Assertion]] = []
        for res in results:
            merged: OrderedSet[ass.Assertion] = OrderedSet()
            for trace in res.assertion_traces.values():
                merged.update(trace.get_assertions(statement))
            assertions.append(merged)

        first, *remainder = assertions
        first.intersection_update(*remainder)
        return first


class MutationAnalysisAssertionGenerator(AssertionGenerator):
    """Uses mutation analysis to filter out less relevant assertions."""

    def __init__(self, executor: ex.TestCaseExecutor):
        super().__init__(executor)
        adapter = ma.MutationAdapter()
        self._mutated_modules = [x for x, _ in adapter.mutate_module()]

    def _execute(
        self, test_cases: list[tc.TestCase]
    ) -> list[tuple[tc.TestCase, list[ex.ExecutionResult]]]:
        tests_and_results = super()._execute(test_cases)

        for idx, mutated_module in enumerate(self._mutated_modules):
            self._logger.info(
                "Running tests on mutant %3i/%i", idx + 1, len(self._mutated_modules)
            )
            self._executor.module_provider.add_mutated_version(
                module_name=config.configuration.module_name,
                mutated_module=mutated_module,
            )
            for test, results in tests_and_results:
                results.append(self._executor.execute(test))

        return tests_and_results

    def _get_assertions_for(
        self, results: list[ex.ExecutionResult], statement: st.Statement
    ) -> OrderedSet[ass.Assertion]:
        # The first executions are from executions on the non-mutated module.
        base_assertions = super()._get_assertions_for(
            results[: self._base_executions], statement
        )

        assertion_counter: dict[ass.Assertion, int] = Counter()
        for mutated_result in results[self._base_executions :]:
            for trace in mutated_result.assertion_traces.values():
                assertion_counter.update(Counter(trace.get_assertions(statement)))

        num_mutations = len(self._mutated_modules)

        # Only assertions that are not found every time are interesting.
        return OrderedSet(
            [
                assertion
                for assertion in base_assertions
                if assertion_counter[assertion] < num_mutations
                or isinstance(
                    assertion, ass.ExceptionAssertion
                )  # exceptions are interesting nonetheless
            ]
        )
