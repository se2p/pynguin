#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides a MIO."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from math import ceil
from typing import TYPE_CHECKING

import pynguin.configuration as config
import pynguin.ga.algorithms.archive as arch
from pynguin.ga.algorithms.generationalgorithm import GenerationAlgorithm
from pynguin.utils import randomness

if TYPE_CHECKING:
    import pynguin.ga.testcasechromosome as tcc
    import pynguin.ga.testsuitechromosome as tsc


@dataclass
class Parameters:
    """Represents the parameters that are adjusted while running the algorithm."""

    # Probability for choosing creating a new test case or sampling an existing one.
    Pr: float = config.configuration.mio.initial_config.random_test_or_from_archive_probability

    # The maximum size of the population kept in the archive per target
    n: int = config.configuration.mio.initial_config.number_of_tests_per_target

    # The number of mutations performed on a test case before sampling again.
    m: int = config.configuration.mio.initial_config.number_of_mutations

    def is_valid(self):
        """Check if the parameters are valid."""
        assert self.Pr >= 0.0
        assert self.n >= 1
        assert self.m >= 1


class MIOAlgorithm(GenerationAlgorithm[arch.MIOArchive]):
    """Implements MIO."""

    _logger = logging.getLogger(__name__)

    def __init__(self) -> None:  # noqa: D107
        super().__init__()
        self._solution: tcc.TestCaseChromosome | None = None
        self._parameters = Parameters()
        self._current_mutations = 0
        self._focused = False

    def generate_tests(self) -> tsc.TestSuiteChromosome:  # noqa: D102
        self.before_search_start()
        while (
            self.resources_left()
            and len(self._test_case_fitness_functions) - self._archive.num_covered_targets != 0
        ):
            self.evolve()
            self._update_parameters()
            self.after_search_iteration(self.create_test_suite(self._archive.solutions))
        self.after_search_finish()
        return self.create_test_suite(self._archive.solutions)

    def _update_parameters(self):
        progress = self.progress()
        progress_until_focused = progress / config.configuration.mio.exploitation_starts_at_percent

        if self._focused:
            # Already in focused phase.
            # Nothing to change.
            return

        n_before = self._parameters.n
        if progress > config.configuration.mio.exploitation_starts_at_percent:
            self._logger.debug("Entering focused phase.")
            self._focused = True
            self._parameters.Pr = (
                config.configuration.mio.focused_config.random_test_or_from_archive_probability
            )
            self._parameters.n = config.configuration.mio.focused_config.number_of_tests_per_target
            self._parameters.m = config.configuration.mio.focused_config.number_of_mutations
        else:
            self._parameters.Pr = MIOAlgorithm._scale(
                config.configuration.mio.initial_config.random_test_or_from_archive_probability,
                config.configuration.mio.focused_config.random_test_or_from_archive_probability,
                progress_until_focused,
            )
            self._parameters.n = ceil(
                MIOAlgorithm._scale(
                    config.configuration.mio.initial_config.number_of_tests_per_target,
                    config.configuration.mio.focused_config.number_of_tests_per_target,
                    progress_until_focused,
                )
            )
            self._parameters.m = ceil(
                MIOAlgorithm._scale(
                    config.configuration.mio.initial_config.number_of_mutations,
                    config.configuration.mio.focused_config.number_of_mutations,
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
            self._current_mutations = 1
        else:
            maybe_offspring = self._archive.get_solution()
            if maybe_offspring is None:
                # Nothing in archive, so sample new one.
                offspring = self.chromosome_factory.get_chromosome()
            else:
                offspring = maybe_offspring
            offspring.mutate()
            self._current_mutations = 1
        if self._archive.update([offspring]):
            self._solution = offspring
