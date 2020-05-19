# This file is part of Pynguin.
#
# Pynguin is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Pynguin is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Pynguin.  If not, see <https://www.gnu.org/licenses/>.
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
