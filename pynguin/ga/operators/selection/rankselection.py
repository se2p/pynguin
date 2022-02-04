#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provide rank selection."""
from __future__ import annotations

from math import sqrt
from typing import TypeVar

import pynguin.configuration as config
import pynguin.ga.chromosome as chrom
from pynguin.ga.operators.selection.selection import SelectionFunction
from pynguin.utils import randomness

T = TypeVar("T", bound=chrom.Chromosome)  # pylint:disable=invalid-name


class RankSelection(SelectionFunction[T]):
    """Rank selection."""

    def get_index(self, population: list[T]) -> int:
        """Provides an index in the population that is chosen by rank selection.

        Make sure that the population is sorted. The fittest chromosomes have to
        come first.

        Args:
            population: A list of chromosomes to select from

        Returns:
            The index that should be used for selection
        """
        random_value = randomness.next_float()
        bias = config.configuration.search_algorithm.rank_bias
        return int(
            len(population)
            * (
                (bias - sqrt(bias**2 - (4.0 * (bias - 1.0) * random_value)))
                / 2.0
                / (bias - 1.0)
            )
        )
