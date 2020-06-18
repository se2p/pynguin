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
"""Provides an abstract base class for chromosomes"""
from __future__ import annotations

import abc
from abc import abstractmethod
from statistics import mean
from typing import Dict, List

import pynguin.ga.fitnessfunction as ff


class Chromosome(metaclass=abc.ABCMeta):
    """An abstract base class for chromosomes"""

    def __init__(self):
        self._fitness_functions: List[ff.FitnessFunction] = []
        self._current_values: Dict[ff.FitnessFunction, ff.FitnessValues] = dict()

        self._number_of_evaluations: int = 0
        self._changed: bool = True

    @abstractmethod
    def size(self) -> int:
        """Return length of individual

        Returns:
            The length of an individual  # noqa: DAR202
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

    def _check_for_new_evaluation(self) -> None:
        """Check if the fitness values need to be evaluated."""
        assert (
            len(self._fitness_functions) > 0
        ), "Cannot evaluate fitness, if no fitness functions are defined."

        if self._changed:
            for fitness_func in self._fitness_functions:
                new_values = fitness_func.compute_fitness_values(self)
                self._update_fitness_values(fitness_func, new_values)
            self._changed = False
            self._number_of_evaluations += 1

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
        self._current_values[fitness_function] = new_value

    def add_fitness_function(self, fitness_function: ff.FitnessFunction,) -> None:
        """Adds a fitness function.

        Args:
            fitness_function: A fitness function
        """
        self._fitness_functions.append(fitness_function)

    def get_fitness(self) -> float:
        """Provide a sum of the current fitness values

        Returns:
            The sum of the current fitness values
        """
        self._check_for_new_evaluation()
        return sum([value.fitness for value in self._current_values.values()])

    def get_fitness_for(self, fitness_function: ff.FitnessFunction) -> float:
        """Returns the fitness values of a specific fitness function.

        Args:
            fitness_function: The fitness function

        Returns:
            Its fitness value
        """
        self._check_for_new_evaluation()
        return self._current_values[fitness_function].fitness

    def get_coverage(self) -> float:
        """Provides the mean coverage value.

        Returns:
            The mean coverage value
        """
        self._check_for_new_evaluation()
        return mean([value.coverage for value in self._current_values.values()])

    def get_coverage_for(self, fitness_function: ff.FitnessFunction) -> float:
        """Provides the coverage value for a certain fitness function

        Args:
            fitness_function: The fitness function who's coverage value shall be
                returned

        Returns:
            The coverage value for the fitness function
        """
        self._check_for_new_evaluation()
        return self._current_values[fitness_function].coverage

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
    def clone(self) -> Chromosome:
        """Create a clone of this chromosome.

        Returns:
            The cloned chromosome  # noqa: DAR202
        """
