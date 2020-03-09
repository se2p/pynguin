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
from math import sqrt
from pynguin.utils import randomness
import pynguin.configuration as config


def rank_selection(population_size: int) -> int:
    """Provides an index in the population that is chosen by rank selection.
    Make sure that the population is sorted. The fittest chromosomes have to
    come first.
    :param population_size: The size of the population from which an index is chosen."""
    random_value = randomness.next_float()
    bias = config.INSTANCE.rank_bias
    return int(
        population_size
        * (
            (bias - sqrt(bias ** 2 - (4.0 * (bias - 1.0) * random_value)))
            / 2.0
            / (bias - 1.0)
        )
    )
