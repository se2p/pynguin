#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides implementations of a ranking function."""
import logging
import sys
from abc import ABCMeta, abstractmethod
from typing import Dict, Generic, List, Optional, Set, TypeVar

import pynguin.configuration as config
import pynguin.ga.chromosome as chrom
import pynguin.ga.fitnessfunction as ff
from pynguin.ga.comparators.dominancecomparator import DominanceComparator
from pynguin.ga.comparators.preferencesortingcomparator import (
    PreferenceSortingComparator,
)
from pynguin.utils import randomness

C = TypeVar("C", bound=chrom.Chromosome)  # pylint: disable=invalid-name


class RankingFunction(Generic[C], metaclass=ABCMeta):
    """Interface for ranking algorithms."""

    @abstractmethod
    def compute_ranking_assignment(
        self, solutions: List[C], uncovered_goals: Set[ff.FitnessFunction]
    ) -> None:
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
        """

    @abstractmethod
    def get_sub_front(self, rank: int) -> List[C]:
        """Returns the sub-front of chromosome objects of the given rank.

        Sub-fronts are ordered starting from 0 in ascending order, i.e., the first
        non-dominated front has rank 0, the next sub-front rank 1 etc.

        Args:
            rank: The sub-front to retrieve

        Returns:
            A list of solutions of a given rank  # noqa: DAR202
        """

    @abstractmethod
    def get_number_of_sub_fronts(self) -> int:
        """Returns the total number of sub-fronts found.

        Returns:
            The total number of sub-fronts found  # noqa: DAR202
        """


class RankBasedPreferenceSorting(RankingFunction, Generic[C]):
    """Ranks the test cases according to the preference criterion defined for MOSA."""

    _logger = logging.getLogger(__name__)

    def __init__(self) -> None:
        self._fronts: Optional[List[List[C]]] = None

    def compute_ranking_assignment(
        self, solutions: List[C], uncovered_goals: Set[ff.FitnessFunction]
    ) -> None:
        if not solutions:
            self._logger.debug("Solution is empty")
            return

        self._fronts = []

        # First apply the "preference sorting" to the first front only then compute
        # the ranks according to the non-dominate sorting algorithm
        zero_front: List[C] = self._get_zero_front(solutions, uncovered_goals)
        self._fronts.append(zero_front)
        front_index = 1

        if len(zero_front) < config.INSTANCE.population:
            ranked_solutions = len(zero_front)
            comparator: DominanceComparator[C] = DominanceComparator(
                goals=uncovered_goals
            )

            remaining: List[C] = []
            remaining.extend(solutions)
            for element in zero_front:
                if element in remaining:
                    remaining.remove(element)

            while ranked_solutions < config.INSTANCE.population and len(remaining) > 0:
                new_front: List[C] = self._get_non_dominated_solutions(
                    remaining, comparator, front_index
                )
                self._fronts.append(new_front)
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
            self._fronts.append(remaining)

    @staticmethod
    def _get_zero_front(
        solutions: List[C], uncovered_goals: Set[ff.FitnessFunction]
    ) -> List[C]:
        zero_front: Set[C] = set()
        for goal in uncovered_goals:
            comparator: PreferenceSortingComparator[C] = PreferenceSortingComparator(
                goal
            )
            best: Optional[C] = None
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
        solutions: List[C], comparator: DominanceComparator[C], front_index: int
    ) -> List[C]:
        front: List[C] = []
        for solution in solutions:
            is_dominated = False
            dominated_solutions: List[C] = []
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

    def get_sub_front(self, rank: int) -> List[C]:
        if self._fronts is None or rank >= len(self._fronts):
            return []
        return self._fronts[rank]

    def get_number_of_sub_fronts(self) -> int:
        assert self._fronts is not None
        return len(self._fronts)


class FastNonDominatedSorting(RankingFunction, Generic[C]):
    """Ranks the test cases according to the preference criterion defined for MOSA."""

    def __init__(self) -> None:
        self._ranking: List[List[C]] = []
        self._new_covered_goals: Dict[ff.FitnessFunction, C] = {}

    def compute_ranking_assignment(
        self, solutions: List[C], uncovered_goals: Set[ff.FitnessFunction]
    ) -> None:
        fronts: List[List[C]] = self._get_next_non_dominated_front(
            solutions, uncovered_goals
        )
        _array_copy(fronts, 0, self._ranking, 0, len(fronts))

    # pylint: disable=too-many-locals, invalid-name, too-many-branches
    @staticmethod
    def _get_next_non_dominated_front(
        solutions: List[C], uncovered_goals: Set[ff.FitnessFunction]
    ) -> List[List[C]]:
        criterion: DominanceComparator[C] = DominanceComparator(goals=uncovered_goals)

        # dominate_me[i] contains the number of solutions dominating i
        dominate_me: List[int] = []

        # i_dominate[k] contains the list of solutions dominated by k
        i_dominate: List[List[int]] = []

        # front[i] contains the list of individuals belonging to the front i
        front: List[List[int]] = []

        # Initialise the fronts
        for i in range(len(solutions) + 1):
            front[i] = []

        # Initialise distance
        for solution in solutions:
            solution.distance = sys.float_info.max

        # -> Fast non-dominated sorting algorithm
        for p, _ in enumerate(solutions):
            # Initialise the list of individuals that i dominate and the number of
            # individuals that dominate me
            i_dominate[p] = []
            dominate_me[p] = 0

        for p in range(len(solutions) - 1):
            # For all q individuals, calculate if p dominates q or vice versa
            for q in range(p + 1, len(solutions)):
                flag_dominate = criterion.compare(solutions[p], solutions[q])

                if flag_dominate == -1:
                    i_dominate[p].append(q)
                    dominate_me[q] += 1
                elif flag_dominate == 1:
                    i_dominate[q].append(p)
                    dominate_me[p] += 1

        for p, _ in enumerate(solutions):
            if dominate_me[p] == 0:
                front[0].append(p)
                solutions[p].rank = 1

        # Obtain the rest of fronts
        i = 0
        while len(front[i]) != 0:
            i += 1
            for next_1 in front[i - 1]:
                for next_2 in i_dominate[next_1]:
                    index = next_2
                    dominate_me[index] -= 1
                    if dominate_me[index] == 0:
                        front[i].append(index)
                        solutions[index].rank = i + 1

        fronts: List[List[C]] = []
        # 0, 1, 2, ..., i-1 are front, then i fronts
        for j in range(i):
            fronts[j] = []
            for next_front in front[j]:
                fronts[j].append(solutions[next_front])

        return fronts

    def get_sub_front(self, rank: int) -> List[C]:
        return self._ranking[rank]

    def get_number_of_sub_fronts(self) -> int:
        return len(self._ranking)


def _array_copy(src, src_pos, dest, dest_pos, length) -> None:
    for i in range(length):
        dest[i + dest_pos] = src[i + src_pos]
