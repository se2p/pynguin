#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
"""Provide tournament selection."""
from typing import List, TypeVar

import pynguin.configuration as config
import pynguin.ga.chromosome as chrom
from pynguin.ga.operators.selection.selection import SelectionFunction
from pynguin.utils import randomness

T = TypeVar("T", bound=chrom.Chromosome)  # pylint: disable=invalid-name


class TournamentSelection(SelectionFunction[T]):
    """Tournament selection."""

    def get_index(self, population: List[T]) -> int:
        new_num = randomness.next_int(lower_bound=0, upper_bound=len(population))
        winner = new_num

        tournament_round = 0

        while tournament_round < config.Configuration.tournament_size - 1:
            new_num = randomness.next_int(lower_bound=0, upper_bound=len(population))
            selected = population[new_num]

            if self._maximize:
                if selected.get_fitness() > population[winner].get_fitness():
                    winner = new_num
            else:
                if selected.get_fitness() < population[winner].get_fitness():
                    winner = new_num

            tournament_round += 1

        return winner
