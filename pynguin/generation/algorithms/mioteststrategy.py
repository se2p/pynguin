#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides a MIO."""
import logging
from math import ceil
from typing import List, Optional, cast

import pynguin.configuration as config
import pynguin.ga.chromosome as chrom
import pynguin.ga.fitnessfunctions.abstracttestcasefitnessfunction as atcff
import pynguin.ga.testcasechromosome as tcc
import pynguin.generation.algorithms.mioarchive as mioa
import pynguin.utils.statistics.statistics as stat
from pynguin.generation.algorithms.testgenerationstrategy import TestGenerationStrategy
from pynguin.generation.algorithms.wraptestsuitemixin import WrapTestSuiteMixin
from pynguin.utils import randomness
from pynguin.utils.statistics.runtimevariable import RuntimeVariable


# pylint: disable=too-few-public-methods
class MIOTestStrategy(TestGenerationStrategy, WrapTestSuiteMixin):
    """Implements MIO."""

    _logger = logging.getLogger(__name__)

    def __init__(self) -> None:
        super().__init__()
        self._solution: Optional[tcc.TestCaseChromosome] = None
        self._pr: float = config.configuration.random_test_or_from_archive_probability
        self._n: int = config.configuration.number_of_test_per_target
        self._archive: mioa.MIOArchive

    def generate_tests(
        self,
    ) -> chrom.Chromosome:
        self._archive = mioa.MIOArchive(
            cast(List[atcff.AbstractTestCaseFitnessFunction], self.fitness_functions)
        )
        generation = 0
        while (
            not self._stopping_condition.is_fulfilled()
            and len(self.fitness_functions) - self._archive.num_covered_targets != 0
        ):
            self.evolve()
            test_suite = self.create_test_suite(self._archive.get_solutions())
            stat.current_individual(test_suite)
            self._logger.info(
                "Generation: %5i. Best fitness: %5f, Best coverage %5f",
                generation,
                test_suite.get_fitness(),
                test_suite.get_coverage(),
            )
            generation += 1
        stat.track_output_variable(RuntimeVariable.AlgorithmIterations, generation)
        return self.create_test_suite(self._archive.get_solutions())

    def evolve(self) -> None:
        """Evolve the current population and replace it with a new one."""

        # From the second step on, MIO will decide to either sample a new test at random
        # (probability Pr), or will choose one existing test in the archive (probability
        # 1 - Pr), copy it, and mutate it.
        #
        # Note: in MIO there is an extra parameter m which controls how many mutations
        # and fitness evaluations should be done on the same individual before sampling
        # a new one.
        if (
            self._solution is None
            or self._solution.num_mutations()
            > config.configuration.max_num_mutations_before_giving_up
            or self._solution.get_number_of_evaluations()
            > config.configuration.max_num_fitness_evaluations_before_giving_up
        ):
            if randomness.next_float() < self._pr:
                test = self.chromosome_factory.get_chromosome()
                self._add_fitness_functions(test)
                if test.size() == 0:
                    # In case we fail to generate a new random test
                    # fetch one from the archive.
                    test = self._archive.get_solution()
            else:
                test = self._archive.get_solution()
                if test is None or test.size() == 0:
                    test = self.chromosome_factory.get_chromosome()
                    self._add_fitness_functions(test)
            assert test is not None and test.size() > 0
            self._solution = test

        assert self._solution is not None
        self._solution.mutate()
        # TODO(fk) except ConstructionFailed exception?

        used_budget = self.progress()
        if used_budget >= config.configuration.exploitation_starts_at_percent:
            self._pr = 0.0
            self._n = 1
        else:
            scale = used_budget / config.configuration.exploitation_starts_at_percent
            self._pr = config.configuration.random_test_or_from_archive_probability - (
                scale * config.configuration.random_test_or_from_archive_probability
            )
            self._n = ceil(
                config.configuration.number_of_test_per_target
                - (scale * config.configuration.number_of_test_per_target)
            )

        assert self._pr >= 0.0
        assert self._n >= 1
        self._archive.update_archive(self._solution)
        self._archive.shrink_solutions(self._n)

    def _add_fitness_functions(self, chromosome: tcc.TestCaseChromosome) -> None:
        for fitness_function in self._fitness_functions:
            chromosome.add_fitness_function(fitness_function)
