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
"""Provides operations for the genetic algorithm."""
from math import floor
from typing import Tuple

from pynguin.generation.algorithms.wspy.testsuite import TestSuite
from pynguin.utils import randomness


def crossover(parent1: TestSuite, parent2: TestSuite) -> Tuple[TestSuite, TestSuite]:
    """Performs a single point relative crossover of the two parents."""
    offspring1 = parent1.clone()
    offspring2 = parent2.clone()

    if parent1.size() > 1 and parent2.size() > 1:
        split_point = randomness.next_float()

        position1 = floor((offspring1.size() - 1) * split_point) + 1
        position2 = floor((offspring2.size() - 1) * split_point) + 1

        new_test_cases1 = (
            offspring1.test_cases[:position1] + offspring2.test_cases[position2:]
        )
        new_test_cases2 = (
            offspring2.test_cases[:position2] + offspring1.test_cases[position1:]
        )

        offspring1.test_cases = new_test_cases1
        offspring2.test_cases = new_test_cases2
    return offspring1, offspring2
