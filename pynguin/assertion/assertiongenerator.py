#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides an assertion generator"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pynguin.assertion.noneassertionobserver as nao
import pynguin.assertion.primitiveassertionobserver as pao
import pynguin.configuration as config
import pynguin.ga.chromosomevisitor as cv
from pynguin.utils import randomness

if TYPE_CHECKING:
    import pynguin.ga.testcasechromosome as tcc
    import pynguin.ga.testsuitechromosome as tsc
    import pynguin.testcase.execution as ex
    import pynguin.testcase.testcase as tc


class AssertionGenerator(cv.ChromosomeVisitor):
    """A simple assertion generator.
    Creates all regression assertions."""

    _logger = logging.getLogger(__name__)

    def __init__(self, executor: ex.TestCaseExecutor):
        """
        Create new assertion generator.

        Args:
            executor: the executor that will be used to execute the test cases.
        """
        self._executor = executor
        self._executor.add_observer(pao.PrimitiveTraceObserver())
        self._executor.add_observer(nao.NoneTraceObserver())

    def visit_test_suite_chromosome(self, chromosome: tsc.TestSuiteChromosome) -> None:
        self.add_assertions(
            [chrom.test_case for chrom in chromosome.test_case_chromosomes]
        )
        self.filter_failing_assertions(
            [chrom.test_case for chrom in chromosome.test_case_chromosomes]
        )

    def visit_test_case_chromosome(self, chromosome: tcc.TestCaseChromosome) -> None:
        self.add_assertions([chromosome.test_case])
        self.filter_failing_assertions([chromosome.test_case])

    def add_assertions(self, test_cases: list[tc.TestCase]) -> None:
        """Adds assertions to the given test cases

        Args:
            test_cases: the test cases for which assertions should be generated.
        """
        for test_case in test_cases:
            self._add_assertions(test_case)

    def _add_assertions(self, test_case: tc.TestCase) -> None:
        """Adds assertions to the given test case.

        Args:
            test_case: the test case for which assertions should be generated.
        """
        result = self._executor.execute(test_case)
        for statement in test_case.statements:
            for _, trace in result.output_traces.items():
                for assertion in trace.get_assertions(statement):
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

    def filter_failing_assertions(self, test_cases: list[tc.TestCase]) -> None:
        """Removes assertions from the given list of test cases, which do not hold in
        every execution.

        Args:
            test_cases: the test cases whose assertions should be filtered.
        """
        tests = list(test_cases)
        # Two more iterations in random order
        for _ in range(2):
            # TODO(fk) Maybe reload module?
            randomness.RNG.shuffle(tests)
            for test in tests:
                self._filter_failing_assertions(test)

    def _filter_failing_assertions(self, test_case: tc.TestCase) -> None:
        result = self._executor.execute(test_case)
        for statement in test_case.statements:
            assertions = set()
            for _, trace in result.output_traces.items():
                assertions.update(trace.get_assertions(statement))
            # Only keep assertions that are contained in both traces.
            # TODO(fk) maybe look at intersection before adding any assertions at all?
            statement.assertions.intersection_update(assertions)
