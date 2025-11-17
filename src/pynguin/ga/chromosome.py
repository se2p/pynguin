#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides an abstract base class for chromosomes."""

from __future__ import annotations

from abc import ABC, abstractmethod

import pynguin.ga.chromosomevisitor as cv
import pynguin.ga.computations as ff


class Chromosome(ABC):  # noqa: PLR0904
    """An abstract base class for chromosomes."""

    def __init__(self, orig: Chromosome | None = None):
        """Initializes the chromosome.

        If a chromosome is given, we clone from that.

        Args:
            orig: Original, if we clone an existing chromosome.
        """
        if orig is None:
            self.computation_cache = ff.ComputationCache(self)
            self.changed: bool = True
            self.distance: float = -1
            self.rank: int = -1
        else:
            self.computation_cache = orig.computation_cache.clone(self)
            self.changed = orig.changed
            self.distance = orig.distance
            self.rank = orig.rank

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

    def get_fitness_functions(self) -> list[ff.FitnessFunction]:
        """Provide the currently configured fitness functions of this chromosome.

        Returns:
            The list of currently configured fitness functions
        """
        return self.computation_cache.get_fitness_functions()

    def add_fitness_function(
        self,
        fitness_function: ff.FitnessFunction,
    ) -> None:
        """Adds a fitness function.

        Args:
            fitness_function: A fitness function
        """
        self.computation_cache.add_fitness_function(fitness_function)

    def get_coverage_functions(self) -> list[ff.CoverageFunction]:
        """Provide the currently configured coverage functions of this chromosome.

        Returns:
            The list of currently configured coverage functions.
        """
        return self.computation_cache.get_coverage_functions()

    def add_coverage_function(
        self,
        coverage_function: ff.CoverageFunction,
    ) -> None:
        """Adds a coverage function.

        Args:
            coverage_function: A fitness function
        """
        self.computation_cache.add_coverage_function(coverage_function)

    def invalidate_cache(self) -> None:
        """Invalidate all cached computation values."""
        self.computation_cache.invalidate_cache()

    def set_fitness_values(self, fitness_values: dict[ff.FitnessFunction, float]) -> None:
        """Sets the fitness values for the specific functions.

        Args:
            fitness_values: A dictionary of fitness values, keyed by fitness function.
        """
        self.computation_cache.set_fitness_values(fitness_values)

    def get_fitness(self) -> float:
        """Provide a sum of the current fitness values.

        Returns:
            The sum of the current fitness values
        """
        return self.computation_cache.get_fitness()

    def get_fitness_for(self, fitness_function: ff.FitnessFunction) -> float:
        """Returns the fitness values of a specific fitness function.

        Args:
            fitness_function: The fitness function

        Returns:
            Its fitness value
        """
        return self.computation_cache.get_fitness_for(fitness_function)

    def get_is_covered(self, fitness_function: ff.FitnessFunction) -> bool:
        """Check if the individual covers this fitness function.

        Args:
            fitness_function: The fitness function to check

        Returns:
            True, iff the individual covers the fitness function.
        """
        return self.computation_cache.get_is_covered(fitness_function)

    def set_coverage_values(self, coverage_values: dict[ff.CoverageFunction, float]) -> None:
        """Sets the coverage values for the specific functions.

        Args:
            coverage_values: A dictionary of coverage values, keyed by coverage function.
        """
        self.computation_cache.set_coverage_values(coverage_values)

    def get_coverage(self) -> float:
        """Provides the mean coverage value.

        Returns:
            The mean coverage value
        """
        return self.computation_cache.get_coverage()

    def get_coverage_for(self, coverage_function: ff.CoverageFunction) -> float:
        """Provides the coverage value for a certain coverage function.

        Args:
            coverage_function: The fitness function whose coverage value shall be
                returned

        Returns:
            The coverage value for the fitness function
        """
        return self.computation_cache.get_coverage_for(coverage_function)

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
