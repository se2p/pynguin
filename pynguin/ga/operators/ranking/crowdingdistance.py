#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides various crowding-distance assignment implementations."""
import sys
from typing import List, Set, TypeVar

import pynguin.ga.chromosome as chrom
import pynguin.ga.fitnessfunction as ff

C = TypeVar("C", bound=chrom.Chromosome)  # pylint: disable=invalid-name


def crowding_distance_assignment(
    front: List[C], goals: Set[ff.FitnessFunction]
) -> None:
    """Assigns traditional crowding distance.

    Args:
        front: Front of non-dominated solutions/tests
        goals: Set of goals/targets (e.g., branches) to consider
    """
    size = len(front)
    if size == 0:
        return
    if size == 1:
        front[0].distance = float("inf")
        return
    if size == 2:
        front[0].distance = float("inf")
        front[1].distance = float("inf")
        return

    for test in front:
        test.distance = 0.0

    for goal in goals:
        # Sort the population by fitness
        front.sort(
            key=lambda t: t.get_fitness_for(goal)  # pylint: disable=cell-var-from-loop
        )

        objective_min_n = front[0].get_fitness_for(goal)
        objective_max_n = front[-1].get_fitness_for(goal)

        # Set crowding distance
        front[0].distance = float("inf")
        front[-1].distance = float("inf")

        for i in range(size - 1):
            distance = front[i + 1].get_fitness_for(goal) - front[
                i - 1
            ].get_fitness_for(goal)
            distance /= objective_max_n - objective_min_n
            distance += front[i].distance
            front[i].distance = distance


def sub_vector_dominance_assignment(
    front: List[C], goals: Set[ff.FitnessFunction]
) -> None:
    """Implements a variant of the crowding distance named "sub-vector dominance
    assignment" proposed by Köppen and Yoshida in:
    Mario Köppen and Kaori Yoshida, "Substitute Distance Assignments in NSGA-II for
    handling Many-objective Optimization Problems", Evolutionary Multi-Criterion
    Optimization, LNCS vol 4403, 2007, pp. 727–741

    Args:
        front: Front of non-dominated solutions/tests
        goals: Set of goals/targets (e.g., branches) to consider
    """
    size = len(front)
    if size == 1:
        front[0].distance = float("inf")
        return

    for test in front:
        test.distance = sys.float_info.max

    for i in range(size - 1):
        element_1 = front[i]
        for j in range(i + 1, size):
            element_2 = front[j]
            dominate_1 = 0
            dominate_2 = 0
            for goal in goals:
                value_1 = element_1.get_fitness_for(goal)
                value_2 = element_2.get_fitness_for(goal)
                if value_1 < value_2:
                    dominate_1 += 1
                elif value_1 > value_2:
                    dominate_2 += 1
            element_1.distance = min(dominate_1, element_1.distance)
            element_2.distance = min(dominate_2, element_2.distance)


def fast_epsilon_dominance_assignment(
    front: List[C], goals: Set[ff.FitnessFunction]
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
        min_set: List[C] = []
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
