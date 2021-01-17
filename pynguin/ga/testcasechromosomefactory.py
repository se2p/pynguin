#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides a factory to create test case chromosomes."""
import pynguin.ga.chromosomefactory as cf
import pynguin.ga.testcasechromosome as tcc
import pynguin.ga.testcasefactory as tcf
import pynguin.testcase.testfactory as tf


class TestCaseChromosomeFactory(
    cf.ChromosomeFactory[tcc.TestCaseChromosome]
):  # pylint:disable=too-few-public-methods.
    """A factory that creates test case chromosomes."""

    def __init__(
        self, test_factory: tf.TestFactory, test_case_factory: tcf.TestCaseFactory
    ) -> None:
        """Instantiates a new factory to create test case chromosomes.

        Args:
            test_factory: The internal factory required for the mutation.
            test_case_factory: The internal test case factory required for creation
                               of test cases.
        """
        self._test_factory = test_factory
        self._test_case_factory = test_case_factory

    def get_chromosome(self) -> tcc.TestCaseChromosome:
        test_case = self._test_case_factory.get_test_case()
        return tcc.TestCaseChromosome(
            test_case=test_case, test_factory=self._test_factory
        )
