#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provide various crossover functions for genetic algorithms."""

from abc import abstractmethod
from math import floor
from typing import Generic, TypeVar

import pynguin.ga.chromosome as chrom
from pynguin.utils import randomness

T = TypeVar("T", bound=chrom.Chromosome)


class CrossOverFunction(Generic[T]):
    """Cross over two individuals."""

    @abstractmethod
    def cross_over(self, parent_1: T, parent_2: T) -> None:
        """Perform a crossover between the two parents.

        Args:
            parent_1: The first parent chromosome
            parent_2: The second parent chromosome
        """


class SinglePointRelativeCrossOver(CrossOverFunction[T]):
    """Performs a single-point relative crossover of the two parents.

    The splitting point is not an absolute but a relative value (e.g., at position 70%
    of n). For example, if n1=10 and n2=20 and the splitting point is 70%, we would have
    position 7 in the first and 14 in the second.

    Therefore, the offspring d has n<=max(n1, n2)
    """

    def cross_over(self, parent_1: T, parent_2: T) -> None:  # noqa: D102
        if parent_1.size() < 2 or parent_2.size() < 2:
            return

        split_point = randomness.next_float()
        pos_1 = floor((parent_1.size() - 1) * split_point) + 1
        pos_2 = floor((parent_2.size() - 1) * split_point) + 1
        clone_1 = parent_1.clone()
        clone_2 = parent_2.clone()
        parent_1.cross_over(clone_2, pos_1, pos_2)
        parent_2.cross_over(clone_1, pos_2, pos_1)
