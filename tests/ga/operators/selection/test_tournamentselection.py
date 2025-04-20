#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
from unittest.mock import MagicMock

import pynguin.ga.chromosome as chrom
import pynguin.ga.operators.selection as sel

from pynguin.utils import randomness


def test_tournament_selection():
    selection = sel.TournamentSelection()
    population = []
    for _ in range(20):
        chromosome = MagicMock(chrom.Chromosome)
        chromosome.get_fitness.return_value = randomness.next_float()
        population.append(chromosome)
    assert 0 <= selection.get_index(population) < len(population)
