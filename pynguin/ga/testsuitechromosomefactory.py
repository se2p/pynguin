#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
import pynguin.configuration as config
import pynguin.ga.chromosomefactory as cf
import pynguin.ga.testcasechromosomefactory as tccf
import pynguin.testsuite.testsuitechromosome as tsc
from pynguin.utils import randomness


class TestSuiteChromosomeFactory(cf.ChromosomeFactory[tsc.TestSuiteChromosome]):
    """A factory that provides new test suite chromosomes of random length."""

    def __init__(self, test_case_chromosome_factory: tccf.TestCaseChromosomeFactory):
        """Instantiates a new factory

        Args:
            test_case_chromosome_factory: The internal test case chromosome factory
        """
        self.test_case_chromosome_factory = test_case_chromosome_factory

    def get_chromosome(self) -> tsc.TestSuiteChromosome:
        chromosome = tsc.TestSuiteChromosome(self.test_case_chromosome_factory)
        num_tests = randomness.next_int(
            config.INSTANCE.min_initial_tests, config.INSTANCE.max_initial_tests + 1
        )

        for _ in range(num_tests):
            chromosome.add_test_case_chromosome(
                self.test_case_chromosome_factory.get_chromosome()
            )

        return chromosome
