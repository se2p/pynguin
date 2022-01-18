#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provide abstract selection function."""
from __future__ import annotations

from abc import abstractmethod
from typing import Generic, TypeVar

import pynguin.ga.chromosome as chrom

# pylint: disable=invalid-name
T = TypeVar("T", bound=chrom.Chromosome)


class SelectionFunction(Generic[T]):
    """Abstract base class for selection functions."""

    def __init__(self) -> None:
        self._maximize = True

    @abstractmethod
    def get_index(self, population: list[T]) -> int:
        """Provide an index within the population.

        Args:
            population: A list of chromosomes, the population

        Returns:
            The index within the population  # noqa: DAR202
        """

    def select(self, population: list[T], number: int = 1) -> list[T]:
        """Return N parents.

        Args:
            population: A list of chromosomes, the population
            number: The number of elements to select

        Returns:
            A list of chromosomes that was selected
        """
        offspring: list[T] = []
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
