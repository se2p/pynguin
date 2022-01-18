#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides a comparator for preference sorting."""
from __future__ import annotations

from typing import TYPE_CHECKING, Generic, TypeVar

import pynguin.ga.chromosome as chrom

if TYPE_CHECKING:
    import pynguin.ga.computations as ff

C = TypeVar("C", bound=chrom.Chromosome)  # pylint: disable=invalid-name


# pylint: disable=too-few-public-methods
class PreferenceSortingComparator(Generic[C]):
    """A comparator for chromosomes based on the fitness value of two objects.

    The comparator only considers the specified test goals.
    """

    def __init__(self, goal: ff.FitnessFunction) -> None:
        self._objective = goal

    # pylint: disable=too-many-return-statements
    def compare(self, solution_1: C | None, solution_2: C | None) -> int:
        """Compare the fitness value of two chromosome objects focusing only on one
        goal.

        Args:
            solution_1: A chromosome
            solution_2: A chromosome

        Returns:
            -1 if fitness of solution_1 is less than fitness of solution_2, 0 if the
            fitness values of both solutions are equal, 1 otherwise
        """
        if solution_1 is None:
            return 1
        if solution_2 is None:
            return -1

        value_1 = solution_1.get_fitness_for(self._objective)
        value_2 = solution_2.get_fitness_for(self._objective)
        if value_1 < value_2:
            return -1
        if value_1 > value_2:
            return 1
        if solution_1.length() < solution_2.length():
            return -1
        if solution_1.length() > solution_2.length():
            return 1
        return 0
