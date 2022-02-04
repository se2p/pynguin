#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides a comparator for dominance comparisons."""
from __future__ import annotations

from typing import Generic, TypeVar

from ordered_set import OrderedSet

import pynguin.ga.chromosome as chrom
import pynguin.ga.computations as ff

C = TypeVar("C", bound=chrom.Chromosome)  # pylint: disable=invalid-name


# pylint: disable=too-few-public-methods
class DominanceComparator(Generic[C]):
    """Implements a comparator to compare chromosomes based on the dominance test."""

    def __init__(
        self,
        *,
        goal: ff.FitnessFunction | None = None,
        goals: OrderedSet[ff.FitnessFunction] | None = None,
    ) -> None:
        if goals is not None:
            self._objectives: OrderedSet[ff.FitnessFunction] | None = goals
        elif goal is not None:
            self._objectives = OrderedSet({goal})
        else:
            self._objectives = None

    # pylint: disable=too-many-return-statements
    def compare(self, chromosome_1: C | None, chromosome_2: C | None) -> int:
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
