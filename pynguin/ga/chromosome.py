#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides an abstract base class for chromosomes"""
from __future__ import annotations

from abc import ABCMeta, abstractmethod

import pynguin.ga.chromosomevisitor as cv
import pynguin.ga.computations as ff


class Chromosome(metaclass=ABCMeta):
    """An abstract base class for chromosomes"""

    def __init__(self, orig: Chromosome | None = None):
        """
        Args:
            orig: Original, if we clone an existing chromosome.
        """
        if orig is None:
            self._computation_cache = ff.ComputationCache(self)
            self._changed: bool = True
            self._distance: float = -1
            self._rank: int = -1
        else:
            self._computation_cache = orig._computation_cache.clone(self)
            self._changed = orig._changed
            self._distance = orig._distance
            self._rank = orig._rank

    @abstractmethod
    def size(self) -> int:
        """Return the size of an individual.
        This should be number of elements it contains.

        Returns:
            The size of an individual  # noqa: DAR202
        """

    @abstractmethod
    def length(self) -> int:
        """Provide the length of an individual.
        This should be the total length of all contained elements and possible
        sub-elements. Look at the implementation to see the difference to size().

        Returns: The length of this individual.
        """

    def has_changed(self) -> bool:
        """Has this chromosome changed since the last evaluation?

        Returns:
            Whether or not this chromosome change since the last evaluation
        """
        return self._changed

    def set_changed(self, changed: bool) -> None:
        """Set changed status to parameter value.

        Args:
            changed: Then change state of this chromosome
        """
        self._changed = changed

    def get_fitness_functions(self) -> list[ff.FitnessFunction]:
        """Provide the currently configured fitness functions of this chromosome.

        Returns:
            The list of currently configured fitness functions
        """
        return self._computation_cache.get_fitness_functions()

    def add_fitness_function(
        self,
        fitness_function: ff.FitnessFunction,
    ) -> None:
        """Adds a fitness function.

        Args:
            fitness_function: A fitness function
        """
        self._computation_cache.add_fitness_function(fitness_function)

    def get_coverage_functions(self) -> list[ff.CoverageFunction]:
        """Provide the currently configured coverage functions of this chromosome.

        Returns:
            The list of currently configured coverage functions.
        """
        return self._computation_cache.get_coverage_functions()

    def add_coverage_function(
        self,
        coverage_function: ff.CoverageFunction,
    ) -> None:
        """Adds a coverage function.

        Args:
            coverage_function: A fitness function
        """
        self._computation_cache.add_coverage_function(coverage_function)

    def invalidate_cache(self) -> None:
        """Invalidate all cached computation values."""
        self._computation_cache.invalidate_cache()

    def get_fitness(self) -> float:
        """Provide a sum of the current fitness values

        Returns:
            The sum of the current fitness values
        """
        return self._computation_cache.get_fitness()

    def get_fitness_for(self, fitness_function: ff.FitnessFunction) -> float:
        """Returns the fitness values of a specific fitness function.

        Args:
            fitness_function: The fitness function

        Returns:
            Its fitness value
        """
        return self._computation_cache.get_fitness_for(fitness_function)

    def get_is_covered(self, fitness_function: ff.FitnessFunction) -> bool:
        """Check if the individual covers this fitness function.

        Args:
            fitness_function: The fitness function to check

        Returns:
            True, iff the individual covers the fitness function.
        """
        return self._computation_cache.get_is_covered(fitness_function)

    def get_coverage(self) -> float:
        """Provides the mean coverage value.

        Returns:
            The mean coverage value
        """
        return self._computation_cache.get_coverage()

    def get_coverage_for(self, coverage_function: ff.CoverageFunction) -> float:
        """Provides the coverage value for a certain coverage function

        Args:
            coverage_function: The fitness function who's coverage value shall be
                returned

        Returns:
            The coverage value for the fitness function
        """
        return self._computation_cache.get_coverage_for(coverage_function)

    @abstractmethod
    def cross_over(self, other: Chromosome, position1: int, position2: int) -> None:
        """Single point cross over.

        This chromosome will be split at `position1`, the other at `position2`,
        and the crossover will be performed with these pre- and suffixes.

        Args:
            other: The other chromosome to perform the crossover with
            position1: The point in the first chromosome
            position2: The point in the second chromosome
        """

    @abstractmethod
    def mutate(self) -> None:
        """Mutate this chromosome."""

    @abstractmethod
    def clone(self) -> Chromosome:
        """Create a clone of this chromosome.

        Returns:
            The cloned chromosome  # noqa: DAR202
        """

    @abstractmethod
    def accept(self, visitor: cv.ChromosomeVisitor) -> None:
        """Accept a chromosome visitor.

        Args:
            visitor: the visitor that is accepted.
        """

    @abstractmethod
    def __eq__(self, other):
        pass

    @abstractmethod
    def __hash__(self):
        pass

    @property
    def distance(self) -> float:
        """Provides the distance value of this chromosome.

        Returns:
            The distance value of this chromosome
        """
        return self._distance

    @distance.setter
    def distance(self, distance: float) -> None:
        """Sets the distance value of this chromosome.

        Args:
            distance: The new distance value
        """
        self._distance = distance

    @property
    def rank(self) -> int:
        """Provide the rank value of this chromosome.

        Returns:
            The rank value of this chromosome
        """
        return self._rank

    @rank.setter
    def rank(self, rank: int) -> None:
        """Sets the rank value of this chromosome.

        Args:
            rank: The new rank value
        """
        self._rank = rank
