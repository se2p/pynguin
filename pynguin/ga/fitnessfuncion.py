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
"""Provides an abstract base class of fitness functions"""
from __future__ import annotations

import logging
from abc import ABCMeta, abstractmethod

import pynguin.ga.chromosome as chrom  # pylint: disable=cyclic-import


class FitnessFunction(metaclass=ABCMeta):
    """Abstract base class of fitness function"""

    _logger = logging.getLogger(__name__)

    @staticmethod
    def update_individual(
        fitness_function: FitnessFunction, individual: chrom.Chromosome, fitness: float,
    ) -> None:
        """Update the fitness values for an individual.

        :param fitness_function: The fitness function
        :param individual: The individual
        :param fitness: The new fitness value
        """
        individual.set_fitness(fitness_function, fitness)
        individual.increase_number_of_evaluations()

    @abstractmethod
    def get_fitness(self, individual: chrom.Chromosome) -> float:
        """Calculate and set fitness function

        :param individual: An individual Chromosome
        :return: the new fitness
        """

    @staticmethod
    def normalise(value: float) -> float:
        """Normalise a value"""
        if value < 0:
            raise RuntimeError("Values to normalise cannot be negative")
        if value == float("inf"):
            return 1.0
        return value / (1.0 + value)

    @abstractmethod
    def is_maximisation_function(self) -> bool:
        """Do we need to maximise or minimise this function?

        :return: A boolean
        """
