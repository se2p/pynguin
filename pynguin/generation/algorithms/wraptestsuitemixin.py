#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides a mixin that wraps test-case chromosomes into a test-suite chromosome."""
from typing import Iterable

import pynguin.ga.fitnessfunction as ff
import pynguin.ga.fitnessfunctions.abstracttestsuitefitnessfunction as atsff
import pynguin.ga.testcasechromosome as tcc
import pynguin.ga.testsuitechromosome as tsc


class WrapTestSuiteMixin:
    """Wraps test-case chromosomes into a test-suite chromosome."""

    def __init__(self) -> None:
        self._test_suite_fitness_function: ff.FitnessFunction

    @property
    def test_suite_fitness_function(self) -> ff.FitnessFunction:
        """Provides access to the fitness function of the test-suite chromosome.

        Returns:
            The fitness function of the test-suite chromosome
        """
        return self._test_suite_fitness_function

    @test_suite_fitness_function.setter
    def test_suite_fitness_function(self, fitness_function: ff.FitnessFunction) -> None:
        assert isinstance(fitness_function, atsff.AbstractTestSuiteFitnessFunction)
        self._test_suite_fitness_function = fitness_function

    def create_test_suite(
        self, population: Iterable[tcc.TestCaseChromosome]
    ) -> tsc.TestSuiteChromosome:
        """Wraps a population of test-case chromosomes in a test-suite chromosome.

        This will add the fitness function attached to this mixin to the resulting
        chromosome.

        Args:
            population: A list of test-case chromosomes

        Returns:
            A test-suite chromosome
        """
        suite = tsc.TestSuiteChromosome()
        suite.add_test_case_chromosomes(list(population))
        suite.add_fitness_function(self._test_suite_fitness_function)
        return suite
