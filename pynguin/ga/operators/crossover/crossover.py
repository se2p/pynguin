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
