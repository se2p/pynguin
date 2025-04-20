#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides comparators for the MOSA derivates."""

from __future__ import annotations

from typing import Generic
from typing import TypeVar

import pynguin.ga.chromosome as chrom
import pynguin.ga.computations as ff

from pynguin.utils.orderedset import OrderedSet


C = TypeVar("C", bound=chrom.Chromosome)


class DominanceComparator(Generic[C]):
    """Implements a comparator to compare chromosomes based on the dominance test."""

    def __init__(
        self,
        *,
        goal: ff.FitnessFunction | None = None,
        goals: OrderedSet[ff.FitnessFunction] | None = None,
    ) -> None:
        """Instantiates the comparator.

        Requires either one fitness function as a goal or a set of fitness functions as
        goals for the comparison.  In case both parameters are given, the implementation
        respects the set of fitness functions as the comparator objective; in case none
        of the parameters is given, the implementation aims to retrieve the fitness
        functions from the first given chromosome in the compare method.

        Args:
            goal: A single fitness function
            goals: A set of fitness functions
        """
        if goals is not None:
            self._objectives: OrderedSet[ff.FitnessFunction] | None = goals
        elif goal is not None:
            self._objectives = OrderedSet({goal})
        else:
            self._objectives = None

    def compare(  # noqa: C901
        self, chromosome_1: C | None, chromosome_2: C | None
    ) -> int:
        """Compares two chromosomes regarding their dominance.

        Args:
            chromosome_1: The first chromosome
            chromosome_2: The second chromosome

        Returns:
            -1 if chromosome_1 dominates chromosome_2; 1 if chromosome_1 is dominated by
            chromosome_2; 0 otherwise
        """
        if chromosome_1 is None:
            return 1
        if chromosome_2 is None:
            return -1

        dominate_1 = False
        dominate_2 = False

        if self._objectives is None:
            self._objectives = OrderedSet(chromosome_1.get_fitness_functions())

        for objective in self._objectives:
            flag = ff.compare(
                chromosome_1.get_fitness_for(objective),
                chromosome_2.get_fitness_for(objective),
            )
            if flag < 0:
                dominate_1 = True
                if dominate_2:
                    return 0
            elif flag > 0:
                dominate_2 = True
                if dominate_1:
                    return 0

        if dominate_1 == dominate_2:
            return 0  # no one dominates the other
        if dominate_1:
            return -1  # chromosome_1 dominates
        return 1  # chromosome_2 dominates


class PreferenceSortingComparator(Generic[C]):
    """A comparator for chromosomes based on the fitness value of two objects.

    The comparator only considers the specified test goals.
    """

    def __init__(self, goal: ff.FitnessFunction) -> None:
        """Initializes the comparator.

        Args:
            goal: The goal to respect for the comparison
        """
        self.__objective = goal

    def compare(self, chromosome_1: C | None, chromosome_2: C | None) -> int:
        """Compare the fitness value of two chromosomes focusing only on one goal.

        Args:
            chromosome_1: A chromosome
            chromosome_2: A chromosome

        Returns:
            -1 if fitness of chromosome_1 is less than fitness of chromosome_2, 0 if the
            fitness values of both solutions are equal, 1 otherwise
        """
        if chromosome_1 is None:
            return 1
        if chromosome_2 is None:
            return -1

        value_1 = chromosome_1.get_fitness_for(self.__objective)
        value_2 = chromosome_2.get_fitness_for(self.__objective)
        if value_1 < value_2:
            return -1
        if value_1 > value_2:
            return 1
        if chromosome_1.length() < chromosome_2.length():
            return -1
        if chromosome_1.length() > chromosome_2.length():
            return 1
        return 0
