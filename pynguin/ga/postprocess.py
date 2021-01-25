#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""
Provides chromosome visitors to perform post processing.
"""

import pynguin.ga.chromosomevisitor as cv
import pynguin.ga.testcasechromosome as tcc
import pynguin.ga.testsuitechromosome as tsc


class ExceptionTruncation(cv.ChromosomeVisitor):
    """Truncates test cases after an exception-raising statement."""

    def visit_test_suite_chromosome(self, chromosome: tsc.TestSuiteChromosome) -> None:
        for test_case_chromosome in chromosome.test_case_chromosomes:
            test_case_chromosome.accept(self)

    def visit_test_case_chromosome(self, chromosome: tcc.TestCaseChromosome) -> None:
        if chromosome.is_failing():
            chop_position = chromosome.get_last_mutatable_statement()
            if chop_position is not None:
                chromosome.test_case.chop(chop_position)
