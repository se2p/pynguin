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
"""Provide abstract selection function."""
from abc import abstractmethod
from typing import Generic, List, TypeVar

import pynguin.ga.chromosome as chrom

# pylint: disable=invalid-name
T = TypeVar("T", bound=chrom.Chromosome)


class SelectionFunction(Generic[T]):
    """Abstract base class for selection functions."""

    def __init__(self) -> None:
        self._maximize = True

    @abstractmethod
    def get_index(self, population: List[T]) -> int:
        """Provide an index within the population.

        Args:
            population: A list of chromosomes, the population

        Returns:
            The index within the population  # noqa: DAR202
        """

    def select(self, population: List[T], number: int = 1) -> List[T]:
        """Return N parents.

        Args:
            population: A list of chromosomes, the population
            number: The index to select

        Returns:
            A list of chromosomes that was selected
        """
        offspring: List[T] = []
        for _ in range(number):
            offspring.append(population[self.get_index(population)])
        return offspring

    @property
    def maximize(self):
        """Do we maximize fitness?

        Returns:
            Whether or not this is a maximising fitness function
        """
        return self._maximize

    @maximize.setter
    def maximize(self, new_value: bool) -> None:
        """Sets whether or not this is a maximising fitness function

        Args:
            new_value: The new value
        """
        self._maximize = new_value
