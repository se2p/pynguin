#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
from unittest.mock import MagicMock

import pynguin.ga.chromosome as chrom
import pynguin.ga.operators.selection.tournamentselection as sel
from pynguin.utils import randomness


def test_tournament_selection():
    selection = sel.TournamentSelection()
    population = []
    for _ in range(20):
        chromosome = MagicMock(chrom.Chromosome)
        chromosome.get_fitness.return_value = randomness.next_float()
        population.append(chromosome)
    assert 0 <= selection.get_index(population) < len(population)
