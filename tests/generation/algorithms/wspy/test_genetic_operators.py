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
from unittest.mock import MagicMock

from pynguin.generation.algorithms.wspy.genetic_operations import crossover


def test_crossover_successful():
    part_one = ["a", "b", "c", "d", "e", "f", "g", "h", "i"]
    part_two = ["1", "2", "3"]

    parent1 = MagicMock(test_cases=part_one)
    parent1.clone.return_value = parent1
    parent1.size.return_value = len(part_one)
    parent2 = MagicMock(test_cases=part_two)
    parent2.clone.return_value = parent2
    parent2.size.return_value = len(part_two)

    offspring1, offspring2 = crossover(parent1, parent2)
    for entry in part_one + part_two:
        assert (
            entry in offspring1.test_cases and entry not in offspring2.test_cases
        ) or (entry not in offspring1.test_cases and entry in offspring2.test_cases)
    assert len(offspring1.test_cases) + len(offspring2.test_cases) == len(
        part_one + part_two
    )


def test_crossover_to_small():
    parent1 = MagicMock()
    parent1.size.return_value = 1
    parent1.clone.return_value = "Test1"
    parent2 = MagicMock()
    parent2.size.return_value = 1
    parent2.clone.return_value = "Test2"

    offspring1, offspring2 = crossover(parent1, parent2)
    assert offspring1 == "Test1"
    assert offspring2 == "Test2"
