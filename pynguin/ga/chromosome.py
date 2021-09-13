#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides an abstract base class for chromosomes"""
from __future__ import annotations

import statistics
from abc import ABCMeta, abstractmethod
from typing import Dict, List, Optional

import pynguin.ga.chromosomevisitor as cv
import pynguin.ga.fitnessfunction as ff


class Chromosome(metaclass=ABCMeta):
    """An abstract base class for chromosomes"""

    def __init__(self, orig: Optional[Chromosome] = None):
        """
        Args:
            orig: Original, if we clone an existing chromosome.
        """
        if orig is None:
            self._fitness_functions: List[ff.FitnessFunction] = []
            self._fitness_values: Dict[ff.FitnessFunction, ff.FitnessValues] = {}
            self._number_of_evaluations: int = 0
            self._changed: bool = True
            self._distance: float = -1
            self._rank: int = -1
        else:
            self._fitness_functions = list(orig._fitness_functions)
            self._fitness_values = dict(orig._fitness_values)
            self._number_of_evaluations = orig._number_of_evaluations
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

    def get_fitness_functions(self) -> List[ff.FitnessFunction]:
        """Provide the currently configured fitness function of this chromosome.

        Returns:
            The list of currently configured fitness functions
        """
        return self._fitness_functions

    def _check_for_new_evaluation(
        self, only: Optional[ff.FitnessFunction] = None
    ) -> None:
        """Check if the fitness values need to be evaluated.

        Args:
            only: Only compute the fitness values for this function.
        """
        assert (
            len(self._fitness_functions) > 0
        ), "Cannot evaluate fitness, if no fitness functions are defined."

        if self._changed:
            # If the chromosome has changed, we invalidate all values computed so far
            self.invalidate_fitness_values()
            # Compute those values in which we are interested.
            self._compute_requested_fitness_values(only)
            self._changed = False
            self._number_of_evaluations += 1
        elif len(self._fitness_values) != len(self._fitness_functions):
            # This condition is for cases, where the chromosome did not change,
            # but we still need to evaluate the fitness again, e.g., because a new
            # fitness function was added, or the way how a fitness function calculates
            # its fitness has changed.
            self._compute_requested_fitness_values(only)

    def _compute_requested_fitness_values(
        self, only: Optional[ff.FitnessFunction] = None
    ):
        for fitness_func in self._fitness_functions if only is None else [only]:
            if fitness_func not in self._fitness_values:
                new_values = fitness_func.compute_fitness_values(self)
                self._update_fitness_values(fitness_func, new_values)

    def _update_fitness_values(
        self, fitness_function: ff.FitnessFunction, new_value: ff.FitnessValues
    ) -> None:
        """Update the fitness values for the given function.

        Args:
            fitness_function: The fitness function to update
            new_value: The new fitness values

        Raises:
            RuntimeError: in case the validation of the new value was not successful
        """
        assert (
            fitness_function in self._fitness_functions
        ), "Cannot update unknown fitness function."

        violations = new_value.validate()
        if len(violations) > 0:
            raise RuntimeError(", ".join(violations))
        self._fitness_values[fitness_function] = new_value

    def invalidate_fitness_values(
        self, only: Optional[ff.FitnessFunction] = None
    ) -> None:
        """Invalidate this chromosome's fitness values.
        This can be necessary if the containing test suite is evaluated.
        In such a case, this chromosome does not need to be run again,
        but it must recompute its fitness values.

        Args:
            only: Invalidate only the values for this function.
        """
        if only is None:
            self._fitness_values.clear()
        else:
            self._fitness_values.pop(only, None)

    def add_fitness_function(
        self,
        fitness_function: ff.FitnessFunction,
    ) -> None:
        """Adds a fitness function.

        Args:
            fitness_function: A fitness function
        """
        assert (
            not fitness_function.is_maximisation_function()
        ), "Currently only minimization is supported"
        self._fitness_functions.append(fitness_function)

    def get_fitness(self) -> float:
        """Provide a sum of the current fitness values

        Returns:
            The sum of the current fitness values
        """
        self._check_for_new_evaluation()
        return sum([value.fitness for value in self._fitness_values.values()])

    def get_fitness_for(self, fitness_function: ff.FitnessFunction) -> float:
        """Returns the fitness values of a specific fitness function.

        Args:
            fitness_function: The fitness function

        Returns:
            Its fitness value
        """
        self._check_for_new_evaluation(fitness_function)
        return self._fitness_values[fitness_function].fitness

    def get_coverage(self) -> float:
        """Provides the mean coverage value.

        Returns:
            The mean coverage value
        """
        self._check_for_new_evaluation()
        return statistics.mean(
            [value.coverage for value in self._fitness_values.values()]
        )

    def get_coverage_for(self, fitness_function: ff.FitnessFunction) -> float:
        """Provides the coverage value for a certain fitness function

        Args:
            fitness_function: The fitness function who's coverage value shall be
                returned

        Returns:
            The coverage value for the fitness function
        """
        self._check_for_new_evaluation(fitness_function)
        return self._fitness_values[fitness_function].coverage

    def get_number_of_evaluations(self):
        """Provide the number of times this chromosome was evaluated.

        Returns:
            The number of times this chromosome was evaluated
        """
        return self._number_of_evaluations

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
