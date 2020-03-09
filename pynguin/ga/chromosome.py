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
import math
from abc import abstractmethod
from typing import Dict

import pynguin.ga.fitnessfuncion as ff


# pylint: disable=too-many-instance-attributes
class Chromosome(metaclass=abc.ABCMeta):
    """An abstract base class for chromosomes"""

    def __init__(self):
        self.fitness_values: Dict[ff.FitnessFunction, float] = dict()
        self.previous_fitness_values: Dict[ff.FitnessFunction, float] = dict()
        self.coverage_values: Dict[ff.FitnessFunction, float] = dict()
        self.nums_covered_goals: Dict[ff.FitnessFunction, int] = dict()
        self.nums_not_covered_goals: Dict[ff.FitnessFunction, int] = dict()
        self.number_of_evaluations: int = 0
        self.changed: bool = True
        self.local_search_applied: bool = False

    @property
    def size(self) -> int:
        """Return length of individual

        :return: The length of an individual
        """
        raise NotImplementedError("Implement abstract method")

    def set_changed(self, changed: bool) -> None:
        """Set changed status to parameter value"""
        self.changed = changed
        self.local_search_applied = False

    @property
    def fitness(self) -> float:
        """Provide the current fitness value"""
        if len(self.fitness_values) > 1:
            return sum(
                [fitness_value for _, fitness_value in self.fitness_values.items()]
            )
        return (
            0.0
            if not self.fitness_values
            else [fitness_value for _, fitness_value in self.fitness_values.items()][0]
        )

    def get_fitness(self, fitness_function: ff.FitnessFunction) -> float:
        """Returns the fitness value of a specific fitness function

        :param fitness_function: The fitness function
        :return: Its fitness value
        """
        return (
            self.fitness_values[fitness_function]
            if fitness_function in self.fitness_values
            else fitness_function.get_fitness(self)
        )

    def set_fitness(self, fitness_function: ff.FitnessFunction, value: float) -> None:
        """Set new fitness value

        :param fitness_function: The fitness function
        :param value: The new fitness value
        """
        if math.isnan(value) or value == float("inf") or value == float("-inf"):
            raise RuntimeError(
                f"Invalid value of Fitness: {value}, Fitness: {fitness_function}"
            )
        if fitness_function not in self.fitness_values:
            self.previous_fitness_values[fitness_function] = value
            self.fitness_values[fitness_function] = value
        else:
            self.previous_fitness_values[fitness_function] = self.fitness_values[
                fitness_function
            ]
            self.fitness_values[fitness_function] = value

    def has_executed_fitness(self, fitness_function: ff.FitnessFunction) -> bool:
        """Checks whether a fitness function has been executed in last iteration"""
        return fitness_function in self.previous_fitness_values

    def add_fitness(
        self,
        fitness_function: ff.FitnessFunction,
        fitness_value: float = 0.0,
        coverage: float = 0.0,
        num_covered_goals: int = 0,
    ) -> None:
        """Adds a fitness function with associated fitness value, coverage value,
        and number of covered goals.

        :param fitness_function: A fitness function
        :param fitness_value: The fitness value for the function
        :param coverage: The coverage value for the function
        :param num_covered_goals: The number of covered goals for the function
        """
        self.fitness_values[fitness_function] = fitness_value
        self.previous_fitness_values[fitness_function] = fitness_value
        self.coverage_values[fitness_function] = coverage
        self.nums_covered_goals[fitness_function] = num_covered_goals
        self.nums_not_covered_goals[fitness_function] = -1

    @property
    def coverage(self) -> float:
        """Provides an average coverage value"""
        cov_sum = sum(
            [coverage_value for _, coverage_value in self.coverage_values.items()]
        )
        coverage = (
            0.0 if not self.coverage_values else cov_sum / len(self.coverage_values)
        )
        assert 0.0 <= coverage <= 1.0, (
            f"Incorrect coverage value {coverage}.  " f"Expected value between 0 and 1."
        )
        return coverage

    @property
    def num_of_covered_goals(self) -> int:
        """Provides the number of all covered goals"""
        return sum([v for _, v in self.nums_covered_goals.items()])

    @property
    def num_of_not_covered_goals(self) -> int:
        """Provides the number of all non-covered goals"""
        return sum([v for _, v in self.nums_not_covered_goals.items()])

    def get_coverage(self, fitness_function: ff.FitnessFunction) -> float:
        """Provides the coverage value for a certain fitness function"""
        return (
            self.coverage_values[fitness_function]
            if fitness_function in self.coverage_values
            else 0.0
        )

    def set_coverage(
        self, fitness_function: ff.FitnessFunction, coverage: float
    ) -> None:
        """Sets the coverage value for a certain fitness function"""
        self.coverage_values[fitness_function] = coverage

    def get_num_covered_goals(self, fitness_function: ff.FitnessFunction) -> int:
        """Provides the number of covered goals for a certain fitness function"""
        return (
            self.nums_covered_goals[fitness_function]
            if fitness_function in self.nums_covered_goals
            else 0
        )

    def set_num_covered_goals(
        self, fitness_function: ff.FitnessFunction, num_covered_goals: int
    ) -> None:
        """Sets the number of covered goals for a certain fitness function"""
        self.nums_covered_goals[fitness_function] = num_covered_goals

    def get_fitness_instance_of(self, type_) -> float:
        """Provides the fitness for a certain subtype of FitnessFunction

        :param type_: A subtype of FitnessFunction
        :return: Its fitness value
        """
        for fitness_function in self.fitness_values.keys():
            if isinstance(fitness_function, type_):
                return self.fitness_values[fitness_function]
        return 0.0

    def get_coverage_instance_of(self, type_) -> float:
        """Provides the coverage for a certain subtype of FitnessFunction

        :param type_: A subtype of FitnessFunction
        :return: Its coverage value
        """
        for fitness_function in self.coverage_values.keys():
            if isinstance(fitness_function, type_):
                return self.coverage_values[fitness_function]
        return 0.0

    def increase_number_of_evaluations(self) -> None:
        """Increases the number of times this chromosome has been evaluated by one"""
        self.number_of_evaluations += 1
