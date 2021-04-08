#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides the archive for MIO."""


from dataclasses import dataclass
from typing import Dict, List, Optional, Set

import pynguin.ga.fitnessfunctions.abstracttestcasefitnessfunction as atcff
import pynguin.ga.testcasechromosome as tcc
from pynguin.ga.fitnessfunctions.fitness_utilities import normalise
from pynguin.utils import randomness


@dataclass(frozen=True)
class PopulationPair:
    """A tuple of h-value and corresponding test case chromosome."""

    # The h-value as described in the MIO paper.
    # pylint: disable=invalid-name
    h: float

    # The test case chromosome.
    test_case_chromosome: tcc.TestCaseChromosome


class Population:
    """The population that is stored per target."""

    def __init__(self, population_size: int) -> None:
        self._counter = 0
        self._capacity = population_size
        # Assumption: These are always sorted.
        self._solutions: List[PopulationPair] = []

    @property
    def counter(self) -> int:
        """How often was a solution sampled from this population since the last
        improvement in the h-value."""
        return self._counter

    @property
    def is_covered(self) -> bool:
        """Is the corresponding target covered."""
        return (
            len(self._solutions) == 1
            and self._capacity == 1
            and self._solutions[0].h == 1.0
        )

    # pylint: disable=invalid-name
    def add_solution(
        self, h: float, test_case_chromosome: tcc.TestCaseChromosome
    ) -> bool:
        """Add the given solution."""
        assert 0.0 <= h <= 1.0
        if h == 0.0:
            # From the MIO paper: if h = 0, the test is not added, regardless of the
            # following conditions.
            return False
        if h < 1.0 and self.is_covered:
            # candidate solution T does not cover the already fully covered target,
            # therefore there is no way it could be any better
            return False

        candidate_solution = PopulationPair(h, test_case_chromosome)
        added = False

        # Does the candidate fully cover the target?
        if h == 1.0:
            # Yes. Has the target been fully covered by a previous solution?
            if self.is_covered:
                current_solution = self._solutions[0]
                if self._is_pair_better_than_current(
                    current_solution, candidate_solution
                ):
                    added = True
                    self._solutions[0] = candidate_solution
            else:
                # as the target is now fully covered by the candidate solution T, from
                # now on there is no need to keep more than one solution, only the
                # single best one. therefore, we can get rid of all solutions (if any)
                # and shrink the number of solutions to only one.
                added = True
                self._capacity = 1
                self._solutions.clear()
                self._solutions.append(candidate_solution)
        else:
            # No, candidate does not fully cover the target.
            # Is there still space for another solution?
            if len(self._solutions) < self._capacity:
                # Yes, there is
                added = True
                self._solutions.append(candidate_solution)
            else:
                worst_solution = self._solutions[-1]
                if self._is_pair_better_than_current(
                    worst_solution, candidate_solution
                ):
                    added = True
                    self._solutions[-1] = candidate_solution
            self._sort_solutions()

        assert len(self._solutions) <= self._capacity
        if added:
            self._counter = 0
        return added

    @property
    def num_solutions(self):
        """The current of number of contained solutions."""
        return len(self._solutions)

    def sample_solution(self) -> Optional[tcc.TestCaseChromosome]:
        """Sample a random solution, if possible."""
        if len(self._solutions) == 0:
            return None
        self._counter += 1
        return randomness.choice(self._solutions).test_case_chromosome

    def get_best_solution_if_any(self) -> Optional[tcc.TestCaseChromosome]:
        """Get the best solution, if there is one."""
        if self.is_covered:
            return self._solutions[0].test_case_chromosome
        return None

    def shrink_population(self, new_population_size) -> None:
        """Shrink the size of the population."""
        assert new_population_size > 0
        if self.is_covered:
            return
        self._capacity = new_population_size
        self._solutions = self._solutions[0:new_population_size]

    def _sort_solutions(self):
        # Desc sort, from highest to lowest h.
        self._solutions.sort(key=lambda c: c.h, reverse=True)

    @staticmethod
    def _is_pair_better_than_current(
        current: PopulationPair, candidate: PopulationPair
    ):
        if current.h > candidate.h:
            return False
        if current.h < candidate.h:
            return True
        return Population._is_better_than_current(
            current.test_case_chromosome, candidate.test_case_chromosome
        )

    @staticmethod
    def _is_better_than_current(
        current: tcc.TestCaseChromosome, candidate: tcc.TestCaseChromosome
    ) -> bool:
        current_result = current.get_last_execution_result()
        candidate_result = candidate.get_last_execution_result()
        if current_result is not None and (
            current_result.timeout or current_result.has_test_exceptions()
        ):
            # If the current solution has a timeout or throws an exception then a
            # solution that does neither is considered better.
            if (
                candidate_result is not None
                and not candidate_result.timeout
                and not candidate_result.has_test_exceptions()
            ):
                return True

        # Compare length otherwise
        return candidate.size() <= current.size()
        # TODO(fk) support other secondary objectives?


class MIOArchive:
    """The archive that is used in MIO."""

    def __init__(
        self, targets: List[atcff.AbstractTestCaseFitnessFunction], initial_size: int
    ):
        self._archive: Dict[atcff.AbstractTestCaseFitnessFunction, Population] = {
            target: Population(initial_size) for target in targets
        }

    def update_archive(self, solution: tcc.TestCaseChromosome) -> bool:
        """Update the archive with the given solution."""
        updated = False
        solution = solution.clone()
        for target in self._archive:
            fitness_value = solution.get_fitness_for(target)
            result = solution.get_last_execution_result()
            assert result is not None
            if result.has_test_exceptions():
                chop_position = solution.get_last_mutatable_statement()
                assert chop_position is not None
                solution.test_case.chop(chop_position)

            updated |= self._archive[target].add_solution(
                1.0 - normalise(fitness_value), solution
            )
        return updated

    def get_solution(self) -> Optional[tcc.TestCaseChromosome]:
        """Get a random solution."""

        # Choose one target at random that has not been covered but contains some
        # solutions. In case there is not any non-covered target with at least one
        # solution, either because all targets have been covered or for the non-covered
        # targets there is not any solution yet, then choose one of the covered targets
        # at random. Thereafter, choose one solution randomly from the list of solutions
        # of the chosen target.
        targets_with_solutions = [
            func
            for func, population in self._archive.items()
            if population.num_solutions > 0
        ]
        if len(targets_with_solutions) == 0:
            # There is not at least one target with at least one solution
            return None

        potential_targets = [
            func
            for func in targets_with_solutions
            if not self._archive[func].is_covered
        ]
        if len(potential_targets) == 0:
            potential_targets = targets_with_solutions

        assert len(potential_targets) > 0

        # We shuffle before, so we don't always pick the same, in case of ties.
        randomness.RNG.shuffle(potential_targets)

        # Instead of choosing a target at random, we choose the one with the lowest
        # counter value. (See Section 3.3 of the paper that describes this archive
        # for more details)
        potential_targets.sort(key=lambda t: self._archive[t].counter)
        sampled = self._archive[potential_targets[0]].sample_solution()
        if sampled is not None:
            sampled = sampled.clone()
        return sampled

    def shrink_solutions(self, new_population_size):
        """Shrink all populations to the new given size."""
        assert new_population_size > 0
        for population in self._archive.values():
            population.shrink_population(new_population_size)

    def get_solutions(self) -> Set[tcc.TestCaseChromosome]:
        """Get all covering solutions found so far."""
        result = set()
        for population in self._archive.values():
            solution = population.get_best_solution_if_any()
            if solution is not None:
                result.add(solution)
        return result

    @property
    def num_covered_targets(self) -> int:
        """The amount of targets that are covered."""
        return len(
            [1 for population in self._archive.values() if population.is_covered]
        )
