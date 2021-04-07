#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides a MIO."""
import logging
from dataclasses import dataclass
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


# pylint: disable=invalid-name
@dataclass
class Parameters:
    """Represents the parameters that are adjusted while running the algorithm."""

    # Probability for choosing creating a new test case or sampling an existing one.
    Pr: float = config.configuration.random_test_or_from_archive_probability_initial

    # The maximum size of the population kept in the archive per target
    n: int = config.configuration.number_of_tests_per_target_initial

    # The number of mutations performed on a test case before sampling again.
    m: int = config.configuration.num_mutations_initial

    def is_valid(self):
        """Check if the parameters are valid."""
        assert self.Pr >= 0.0
        assert self.n >= 1
        assert self.m >= 1


# pylint: disable=too-few-public-methods
class MIOTestStrategy(TestGenerationStrategy, WrapTestSuiteMixin):
    """Implements MIO."""

    _logger = logging.getLogger(__name__)

    def __init__(self) -> None:
        super().__init__()
        self._solution: Optional[tcc.TestCaseChromosome] = None
        self._archive: mioa.MIOArchive
        self._parameters = Parameters()
        self._current_mutations = 0
        self._focused = False

    def generate_tests(
        self,
    ) -> chrom.Chromosome:
        self._archive = mioa.MIOArchive(
            cast(List[atcff.AbstractTestCaseFitnessFunction], self.fitness_functions),
            self._parameters.n,
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
            self._update_parameters()
            generation += 1
        stat.track_output_variable(RuntimeVariable.AlgorithmIterations, generation)
        return self.create_test_suite(self._archive.get_solutions())

    def _update_parameters(self):
        progress = self.progress()
        progress_until_focused = (
            progress / config.configuration.exploitation_starts_at_percent
        )
        if self._focused:
            return

        n_before = self._parameters.n
        if progress > config.configuration.exploitation_starts_at_percent:
            self._focused = True
            self._parameters.Pr = (
                config.configuration.random_test_or_from_archive_probability_focused
            )
            self._parameters.n = config.configuration.number_of_tests_per_target_focused
            self._parameters.m = config.configuration.num_mutations_focused
        else:
            self._parameters.Pr = MIOTestStrategy._scale(
                config.configuration.random_test_or_from_archive_probability_initial,
                config.configuration.random_test_or_from_archive_probability_focused,
                progress_until_focused,
            )
            self._parameters.n = ceil(
                MIOTestStrategy._scale(
                    config.configuration.number_of_tests_per_target_initial,
                    config.configuration.number_of_tests_per_target_focused,
                    progress_until_focused,
                )
            )
            self._parameters.m = ceil(
                MIOTestStrategy._scale(
                    config.configuration.num_mutations_initial,
                    config.configuration.num_mutations_focused,
                    progress_until_focused,
                )
            )
        self._parameters.is_valid()
        if n_before != self._parameters.n:
            self._archive.shrink_solutions(self._parameters.n)

    @staticmethod
    def _scale(initial, focused, progress_until_focused):
        return initial + (focused - initial) * progress_until_focused

    def evolve(self) -> None:
        """Evolve the current population and replace it with a new one."""

        # From the second step on, MIO will decide to either sample a new test at random
        # (probability Pr), or will choose one existing test in the archive (probability
        # 1 - Pr), copy it, and mutate it.
        #
        # Note: in MIO there is an extra parameter m which controls how many mutations
        # and fitness evaluations should be done on the same individual before sampling
        # a new one.
        if self._solution is not None and self._current_mutations < self._parameters.m:
            offspring = self._solution.clone()
            offspring.mutate()
            self._current_mutations += 1
        elif randomness.next_float() < self._parameters.Pr:
            offspring = self.chromosome_factory.get_chromosome()
            self._add_fitness_functions(offspring)
            self._current_mutations = 1
        else:
            maybe_offspring = self._archive.get_solution()
            if maybe_offspring is None:
                # Nothing in archive, so sample new one.
                offspring = self.chromosome_factory.get_chromosome()
                self._add_fitness_functions(offspring)
            else:
                offspring = maybe_offspring
            offspring.mutate()
            self._current_mutations = 1
        if self._archive.update_archive(offspring):
            self._solution = offspring

    def _add_fitness_functions(self, chromosome: tcc.TestCaseChromosome) -> None:
        for fitness_function in self._fitness_functions:
            chromosome.add_fitness_function(fitness_function)
