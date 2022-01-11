#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides a converter to unify generation results."""
from __future__ import annotations

from typing import TYPE_CHECKING

import pynguin.ga.chromosomevisitor as cv
import pynguin.ga.testsuitechromosome as tsc

if TYPE_CHECKING:
    import pynguin.ga.testcasechromosome as tcc


class ChromosomeConverter(cv.ChromosomeVisitor):
    """
    A chromosome visitor that collects any chromosomes and partitions them
    into a failing and passing test suite chromosome.

    The passing test suite contains only those test cases that did not raise an
    exception during execution.  The failing test suite the remaining test cases.
    TODO(sl) Take care for test cases that raise an exception on purpose.
    """

    def __init__(self):
        """Create new chromosome converter."""
        # TODO(fk) Need to handle fitness functions.
        self._failing_test_suite = tsc.TestSuiteChromosome()
        self._passing_test_suite = tsc.TestSuiteChromosome()

    @property
    def passing_test_suite(self) -> tsc.TestSuiteChromosome:
        """Provides the test suite chromosome containing the passing test cases

        Returns:
            the test suite with the passing test cases
        """
        return self._passing_test_suite

    @property
    def failing_test_suite(self) -> tsc.TestSuiteChromosome:
        """Provides the test suite chromosome containing the failing test cases

        Returns:
            the test suite with the failing test cases
        """
        return self._failing_test_suite

    def visit_test_suite_chromosome(self, chromosome: tsc.TestSuiteChromosome) -> None:
        for test_case_chromosome in chromosome.test_case_chromosomes:
            test_case_chromosome.accept(self)

    def visit_test_case_chromosome(self, chromosome: tcc.TestCaseChromosome) -> None:
        if chromosome.is_failing():
            self._failing_test_suite.add_test_case_chromosome(chromosome.clone())
        else:
            self._passing_test_suite.add_test_case_chromosome(chromosome.clone())
