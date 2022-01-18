#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provide various crossover functions for genetic algorithms."""
from abc import abstractmethod
from typing import Generic, TypeVar

import pynguin.ga.chromosome as chrom

# pylint: disable=invalid-name
T = TypeVar("T", bound=chrom.Chromosome)


# pylint: disable=too-few-public-methods
class CrossOverFunction(Generic[T]):
    """Cross over two individuals."""

    @abstractmethod
    def cross_over(self, parent1: T, parent2: T):
        """Perform a crossover between the two parents.

        Args:
            parent1: The first parent chromosome
            parent2: The second parent chromosome
        """
