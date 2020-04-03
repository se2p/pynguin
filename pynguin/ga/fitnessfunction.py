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

import dataclasses
import logging
import math
from abc import ABCMeta, abstractmethod
from typing import List


@dataclasses.dataclass
class FitnessValues:
    """Fitness related values."""

    fitness: float
    coverage: float

    def validate(self) -> List[str]:
        """Validates the given data. If it is invalid, the returned list contains the violations."""
        violations: List[str] = []
        if math.isnan(self.fitness) or math.isinf(self.fitness) or self.fitness < 0:
            violations.append(f"Invalid value of fitness: {self.fitness}")
        if (
            math.isnan(self.coverage)
            or math.isinf(self.coverage)
            or self.coverage < 0
            or self.coverage > 1
        ):
            violations.append(f"Invalid value for coverage: {self.fitness}")
        return violations


class FitnessFunction(metaclass=ABCMeta):
    """Abstract base class of a fitness function"""

    _logger = logging.getLogger(__name__)

    def __init__(self, executor) -> None:
        """Create new fitness function.
        :param executor: Executor that will be used by the fitness function
        to execute chromosomes."""
        self._executor = executor

    @abstractmethod
    def compute_fitness_values(self, individual) -> FitnessValues:
        """Calculate the new fitness values.

        :param individual: An individual Chromosome
        :return: the new fitness values
        """

    @staticmethod
    def normalise(value: float) -> float:
        """Normalise a value"""
        if value < 0:
            raise RuntimeError("Values to normalise cannot be negative")
        if math.isinf(value):
            return 1.0
        return value / (1.0 + value)

    @abstractmethod
    def is_maximisation_function(self) -> bool:
        """Do we need to maximise or minimise this function?

        :return: A boolean
        """
