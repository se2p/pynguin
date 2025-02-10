#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides archives to store found solutions."""

from __future__ import annotations

import logging
import sys

from abc import ABC
from abc import abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pynguin.ga.computations as ff
import pynguin.ga.testcasechromosome as tcc

from pynguin.utils import randomness
from pynguin.utils.orderedset import OrderedSet


if TYPE_CHECKING:
    from collections.abc import Callable
    from collections.abc import Iterable


class Archive(ABC):
    """Abstract base class for archives that store individuals."""

    _logger = logging.getLogger(__name__)

    def __init__(self):  # noqa: D107
        self._on_target_covered_callbacks: list[Callable[[ff.TestCaseFitnessFunction], None]] = []

    @abstractmethod
    def update(self, solutions: Iterable[tcc.TestCaseChromosome]) -> bool:
        """Updates this archive with the given set of solutions.

        In detail, when a solution manages to satisfy a previously uncovered target,
        it is stored in the archive.  If a target is already covered by one solution
        in the archive, and the given list contains another solution that covers the
        same target, the shorter of the two solutions is retained.  Otherwise,
        the solution is discarded.

        Args:
            solutions: The solutions to update the archive with

        Returns:
            True, iff a solution was stored.
        """

    @property
    @abstractmethod
    def solutions(self) -> OrderedSet[tcc.TestCaseChromosome]:
        """Provides the best solutions found so far.

        Best solutions are those shortest test cases covering one of the targets
        managed by this archive.  Duplicates are eliminated.

        Returns:
            The best solutions in the archive
        """

    def add_on_target_covered(self, callback: Callable[[ff.TestCaseFitnessFunction], None]) -> None:
        """Register a callback for whenever a new target is covered for the first time.

        Args:
            callback: The call back to be registered.
        """
        self._on_target_covered_callbacks.append(callback)

    def _on_target_covered(self, target: ff.TestCaseFitnessFunction) -> None:
        self._logger.debug("Target covered: %s", target)
        for callback in self._on_target_covered_callbacks:
            callback(target)


class CoverageArchive(Archive):
    """Implements the archive used by MOSA.

    The archive is used to store the shortest covering test cases found so far.  It
    also keeps track of which targets are yet to cover.

    For each objective of MOSA, the archive stores the chromosome which covers that
    objective.  Furthermore, when two chromosomes cover the same objective,
    the archive retains the smaller of the two, thus automatically optimising for the
    test case length as secondary criterion.

    It is imperative to know the best possible fitness value for a given fitness
    function.  Otherwise, the archive cannot determine whether or not the target has
    been reached.  Therefore, we limit ourselves to minimising fitness functions and
    assume 0.0 the best possible value.  This does not restrict generality as it is
    trivial to convert from maximising to minimising fitness functions.
    """

    _logger = logging.getLogger(__name__)

    def __init__(  # noqa: D107
        self, objectives: OrderedSet[ff.TestCaseFitnessFunction]
    ) -> None:
        super().__init__()
        self._covered: dict[ff.TestCaseFitnessFunction, tcc.TestCaseChromosome] = {}
        self._uncovered = OrderedSet(objectives)
        self._objectives = OrderedSet(objectives)

    def update(self, solutions: Iterable[tcc.TestCaseChromosome]) -> bool:
        """Updates this archive with the given set of solutions.

        In detail, when a solution manages to satisfy a previously uncovered target,
        it is stored in the archive.  If a target is already covered by one solution
        in the archive, and the given list contains another solution that covers the
        same target, the shorter of the two solutions is retained.  Otherwise,
        the solution is discarded.

        Args:
            solutions: The solutions to update the archive with
        """
        updated = False
        for objective in self._objectives:
            best_solution = self._covered.get(objective, None)
            best_size = sys.maxsize if best_solution is None else best_solution.size()

            for solution in solutions:
                covers = solution.get_is_covered(objective)
                size = solution.size()

                if covers and size < best_size:
                    updated = True
                    self._covered[objective] = solution
                    best_size = size
                    if objective in self._uncovered:
                        self._uncovered.remove(objective)
                        self._on_target_covered(objective)
        self._logger.debug("ArchiveCoverageGoals: %d", len(self._covered))
        return updated

    @property
    def uncovered_goals(self) -> OrderedSet[ff.TestCaseFitnessFunction]:
        """Provides the set of goals that are yet to cover.

        Returns:
            The uncovered goals
        """
        return self._uncovered

    @property
    def covered_goals(self) -> OrderedSet[ff.TestCaseFitnessFunction]:
        """Provides the set of goals that are already covered.

        Returns:
            The covered goals
        """
        return OrderedSet(self._covered.keys())

    @property
    def objectives(self) -> OrderedSet[ff.TestCaseFitnessFunction]:
        """Provides the set of all objectives.

        Returns:
            All objectives
        """
        return self._objectives

    def add_goals(self, new_goals: OrderedSet[ff.TestCaseFitnessFunction]) -> None:
        """Add goals to the archive to consider."""
        for goal in new_goals:
            if goal not in self._objectives:
                self._logger.debug("Adding goal: %s", goal)
                self._objectives.add(goal)
                self._uncovered.add(goal)

    @property
    def solutions(self) -> OrderedSet[tcc.TestCaseChromosome]:  # noqa: D102
        assert self._all_covered(), "Some covered targets have a fitness != 0.0"
        return OrderedSet(self._covered.values())

    def reset(self) -> None:
        """Resets the archive."""
        self._uncovered.update(self._objectives)
        self._covered.clear()

    def _all_covered(self) -> bool:
        return all(
            chromosome.get_is_covered(fitness_function)
            for fitness_function, chromosome in self._covered.items()
        )


@dataclass(frozen=True)
class MIOPopulationPair:
    """A tuple of h-value and corresponding test case chromosome."""

    # The h-value as described in the MIO paper.

    h: float

    # The test case chromosome.
    test_case_chromosome: tcc.TestCaseChromosome


class MIOPopulation:
    """The population that is stored per target."""

    def __init__(self, population_size: int) -> None:  # noqa: D107
        self._counter = 0
        self._capacity = population_size
        # Assumption: These are always sorted.
        self._solutions: list[MIOPopulationPair] = []

    @property
    def counter(self) -> int:
        """Number of solution sampled from this population.

        Measured since the last improvement in the h-value.
        """
        return self._counter

    @property
    def is_covered(self) -> bool:
        """Is the corresponding target covered."""
        return len(self._solutions) == 1 and self._capacity == 1 and self._solutions[0].h == 1.0

    def add_solution(self, h: float, test_case_chromosome: tcc.TestCaseChromosome) -> bool:
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

        candidate_solution = MIOPopulationPair(h, test_case_chromosome)
        added = False

        # Does the candidate fully cover the target?
        if h == 1.0:
            # Yes. Has the target been fully covered by a previous solution?
            if self.is_covered:
                current_solution = self._solutions[0]
                if self._is_pair_better_than_current(current_solution, candidate_solution):
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
                if self._is_pair_better_than_current(worst_solution, candidate_solution):
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

    def sample_solution(self) -> tcc.TestCaseChromosome | None:
        """Sample a random solution, if possible."""
        if len(self._solutions) == 0:
            return None
        self._counter += 1
        return randomness.choice(self._solutions).test_case_chromosome

    def get_best_solution_if_any(self) -> tcc.TestCaseChromosome | None:
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
    def _is_pair_better_than_current(current: MIOPopulationPair, candidate: MIOPopulationPair):
        if current.h > candidate.h:
            return False
        if current.h < candidate.h:
            return True
        return MIOPopulation._is_better_than_current(
            current.test_case_chromosome, candidate.test_case_chromosome
        )

    @staticmethod
    def _is_better_than_current(
        current: tcc.TestCaseChromosome, candidate: tcc.TestCaseChromosome
    ) -> bool:
        current_result = current.get_last_execution_result()
        candidate_result = candidate.get_last_execution_result()
        if current_result is not None and (  # noqa: SIM102
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


class MIOArchive(Archive):
    """The archive that is used in MIO."""

    def __init__(  # noqa: D107
        self,
        targets: OrderedSet[ff.TestCaseFitnessFunction],
        initial_size: int,
    ):
        super().__init__()
        self._archive: dict[ff.TestCaseFitnessFunction, MIOPopulation] = {
            target: MIOPopulation(initial_size) for target in targets
        }

    def update(self, solutions: Iterable[tcc.TestCaseChromosome]) -> bool:
        """Update the archive with the given solutions."""
        updated = False
        for solution in solutions:
            solution_clone = solution.clone()
            for target in self._archive:
                fitness_value = solution_clone.get_fitness_for(target)
                result = solution_clone.get_last_execution_result()
                assert result is not None
                if result.has_test_exceptions():
                    chop_position = solution_clone.get_last_mutatable_statement()
                    assert chop_position is not None
                    solution_clone.test_case.chop(chop_position)
                covered_before = self._archive[target].is_covered
                updated |= self._archive[target].add_solution(
                    1.0 - ff.normalise(fitness_value), solution_clone
                )
                # The goal was covered with this solution
                # TODO(fk) replace with goal.is_covered?
                if not covered_before and self._archive[target].is_covered:
                    self._on_target_covered(target)
        return updated

    def get_solution(self) -> tcc.TestCaseChromosome | None:
        """Get a random solution."""
        # Choose one target at random that has not been covered but contains some
        # solutions. In case there is not any non-covered target with at least one
        # solution, either because all targets have been covered or for the non-covered
        # targets there is not any solution yet, then choose one of the covered targets
        # at random. Thereafter, choose one solution randomly from the list of solutions
        # of the chosen target.
        targets_with_solutions = [
            func for func, population in self._archive.items() if population.num_solutions > 0
        ]
        if len(targets_with_solutions) == 0:
            # There is not at least one target with at least one solution
            return None

        potential_targets = [
            func for func in targets_with_solutions if not self._archive[func].is_covered
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

    @property
    def solutions(self) -> OrderedSet[tcc.TestCaseChromosome]:  # noqa: D102
        result: OrderedSet[tcc.TestCaseChromosome] = OrderedSet()
        for population in self._archive.values():
            solution = population.get_best_solution_if_any()
            if solution is not None:
                result.add(solution)
        return result

    @property
    def num_covered_targets(self) -> int:
        """The amount of targets that are covered."""
        return len([1 for population in self._archive.values() if population.is_covered])
