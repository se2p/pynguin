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
"""Provide rank selection."""
from math import sqrt
from typing import List, TypeVar

import pynguin.configuration as config
import pynguin.ga.chromosome as chrom
from pynguin.ga.operators.selection.selection import SelectionFunction
from pynguin.utils import randomness

T = TypeVar("T", bound=chrom.Chromosome)  # pylint:disable=invalid-name


class RankSelection(SelectionFunction[T]):
    """Rank selection."""

    def get_index(self, population: List[T]) -> int:
        """Provides an index in the population that is chosen by rank selection.

        Make sure that the population is sorted. The fittest chromosomes have to
        come first.

        Args:
            population: A list of chromosomes to select from

        Returns:
            The index that should be used for selection
        """
        random_value = randomness.next_float()
        bias = config.INSTANCE.rank_bias
        return int(
            len(population)
            * (
                (bias - sqrt(bias ** 2 - (4.0 * (bias - 1.0) * random_value)))
                / 2.0
                / (bias - 1.0)
            )
        )
