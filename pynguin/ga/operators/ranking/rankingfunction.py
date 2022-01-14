#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides implementations of a ranking function."""
from __future__ import annotations

import logging
from abc import ABCMeta, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Generic, TypeVar

from ordered_set import OrderedSet

import pynguin.configuration as config
import pynguin.ga.chromosome as chrom
from pynguin.ga.comparators.dominancecomparator import DominanceComparator
from pynguin.ga.comparators.preferencesortingcomparator import (
    PreferenceSortingComparator,
)
from pynguin.utils import randomness

if TYPE_CHECKING:
    import pynguin.ga.computations as ff

C = TypeVar("C", bound=chrom.Chromosome)  # pylint: disable=invalid-name


@dataclass
class RankedFronts(Generic[C]):
    """Contains the ranked fronts."""

    fronts: list[list[C]] | None = None

    def get_sub_front(self, rank: int) -> list[C]:
        """Returns the sub-front of chromosome objects of the given rank.

        Sub-fronts are ordered starting from 0 in ascending order, i.e., the first
        non-dominated front has rank 0, the next sub-front rank 1 etc.

        Args:
            rank: The sub-front to retrieve

        Returns:
            A list of solutions of a given rank
        """
        if self.fronts is None or rank >= len(self.fronts):
            return []
        return self.fronts[rank]

    def get_number_of_sub_fronts(self) -> int:
        """Returns the total number of sub-fronts found.

        Returns:
            The total number of sub-fronts found
        """
        assert self.fronts is not None
        return len(self.fronts)


# pylint: disable=too-few-public-methods
class RankingFunction(Generic[C], metaclass=ABCMeta):
    """Interface for ranking algorithms."""

    @abstractmethod
    def compute_ranking_assignment(
        self, solutions: list[C], uncovered_goals: OrderedSet[ff.FitnessFunction]
    ) -> RankedFronts:
        """Computes the ranking assignment for the given population of solutions.

        The computation is done with respect to the given set of coverage goals.
        More precisely, every individual in the population is assigned to a specific
        dominance front, which can afterwards be retrieved by calling `get_sub_front(
        int)`.  The concrete dominance comparator used for computing the ranking is
        defined by subclasses implementing this interface.

        Args:
            solutions: The population to rank
            uncovered_goals: The set of coverage goals to consider for the ranking
                             assignment

        Returns:
            The ranked fronts
        """


# pylint: disable=too-few-public-methods
class RankBasedPreferenceSorting(RankingFunction, Generic[C]):
    """Ranks the test cases according to the preference criterion defined for MOSA."""

    _logger = logging.getLogger(__name__)

    def compute_ranking_assignment(
        self, solutions: list[C], uncovered_goals: OrderedSet[ff.FitnessFunction]
    ) -> RankedFronts:
        if not solutions:
            self._logger.debug("Solution is empty")
            return RankedFronts()

        fronts = []

        # First apply the "preference sorting" to the first front only then compute
        # the ranks according to the non-dominate sorting algorithm
        zero_front: list[C] = self._get_zero_front(solutions, uncovered_goals)
        fronts.append(zero_front)
        front_index = 1

        if len(zero_front) < config.configuration.search_algorithm.population:
            ranked_solutions = len(zero_front)
            comparator: DominanceComparator[C] = DominanceComparator(
                goals=uncovered_goals
            )

            remaining: list[C] = []
            remaining.extend(solutions)
            for element in zero_front:
                if element in remaining:
                    remaining.remove(element)

            while (
                ranked_solutions < config.configuration.search_algorithm.population
                and len(remaining) > 0
            ):
                new_front: list[C] = self._get_non_dominated_solutions(
                    remaining, comparator, front_index
                )
                fronts.append(new_front)
                for element in new_front:
                    if element in remaining:
                        remaining.remove(element)
                ranked_solutions += len(new_front)
                front_index += 1

        else:
            remaining = []
            remaining.extend(solutions)
            for element in zero_front:
                if element in remaining:
                    remaining.remove(element)
            for element in remaining:
                element.rank = front_index
            fronts.append(remaining)

        return RankedFronts(fronts)

    @staticmethod
    def _get_zero_front(
        solutions: list[C], uncovered_goals: OrderedSet[ff.FitnessFunction]
    ) -> list[C]:
        zero_front: OrderedSet[C] = OrderedSet()
        for goal in uncovered_goals:
            comparator: PreferenceSortingComparator[C] = PreferenceSortingComparator(
                goal
            )
            best: C | None = None
            for solution in solutions:
                flag = comparator.compare(solution, best)
                if flag < 0 or (flag == 0 and randomness.next_bool()):
                    best = solution
            assert best is not None

            best.rank = 0
            zero_front.add(best)
        return list(zero_front)

    @staticmethod
    def _get_non_dominated_solutions(
        solutions: list[C], comparator: DominanceComparator[C], front_index: int
    ) -> list[C]:
        front: list[C] = []
        for solution in solutions:
            is_dominated = False
            dominated_solutions: list[C] = []
            for best in front:
                flag = comparator.compare(solution, best)
                if flag < 0:
                    dominated_solutions.append(best)
                if flag > 0:
                    is_dominated = True
                    break
            if is_dominated:
                continue

            solution.rank = front_index
            front.append(solution)
            for dominated_solution in dominated_solutions:
                if dominated_solution in front:
                    front.remove(dominated_solution)
        return front
