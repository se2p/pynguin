#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides a single point relative crossover."""
from math import floor
from typing import TypeVar

import pynguin.ga.chromosome as chrom
from pynguin.ga.operators.crossover.crossover import CrossOverFunction
from pynguin.utils import randomness

# pylint:disable=invalid-name
T = TypeVar("T", bound=chrom.Chromosome)


# pylint:disable=too-few-public-methods
class SinglePointRelativeCrossOver(CrossOverFunction[T]):
    """Performs a single point relative crossover of the two parents.

    The splitting point is not an absolute value but a relative value (eg, at
    position 70% of n). For example, if n1=10 and n2=20 and splitting point
    is 70%, we would have position 7 in the first and 14 in the second.
    Therefore, the offspring d have n<=max(n1,n2)
    """

    def cross_over(self, parent1: T, parent2: T):
        if parent1.size() < 2 or parent2.size() < 2:
            return

        split_point = randomness.next_float()
        position1 = floor((parent1.size() - 1) * split_point) + 1
        position2 = floor((parent2.size() - 1) * split_point) + 1
        clone1 = parent1.clone()
        clone2 = parent2.clone()
        parent1.cross_over(clone2, position1, position2)
        parent2.cross_over(clone1, position2, position1)
