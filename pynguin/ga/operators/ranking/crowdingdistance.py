#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides various crowding-distance assignment implementations."""
from __future__ import annotations

import sys
from typing import TYPE_CHECKING, TypeVar

from ordered_set import OrderedSet

import pynguin.ga.chromosome as chrom

if TYPE_CHECKING:
    import pynguin.ga.computations as ff

C = TypeVar("C", bound=chrom.Chromosome)  # pylint: disable=invalid-name


def fast_epsilon_dominance_assignment(
    front: list[C], goals: OrderedSet[ff.FitnessFunction]
) -> None:
    """Implements a "fast" version of the variant of the crowding distance.

    It is named "epsilon-dominance-assignment" and was proposed by Köppen and Yoshida in
    Mario Köppen and Kaori Yoshida, "Substitute Distance Assignments in NSGA-II for
    handling Many-objective Optimization Problems", Evolutionary Multi-Croterion
    Optimization, LNCS vol. 4403, 2007, pp. 727–741.

    Args:
        front: Front of non-dominated solutions/tests
        goals: Set of goals/targets (e.g., branches) to consider
    """
    for test in front:
        test.distance = 0

    for goal in goals:
        minimum = sys.float_info.max
        min_set: list[C] = []
        maximum = 0.0
        for test in front:
            value = test.get_fitness_for(goal)
            if value < minimum:
                minimum = value
                min_set.clear()
                min_set.append(test)
            elif value == minimum:
                min_set.append(test)

            if value > maximum:
                maximum = value

        if maximum == minimum:
            continue

        for test in min_set:
            numerator = len(front) - len(min_set)
            denominator = len(front)
            test.distance = max(test.distance, numerator / denominator)
