#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
from unittest.mock import MagicMock

import pynguin.ga.chromosome as chrom
import pynguin.ga.operators.selection.rankselection as ranksel


def test_rank_selection():
    selection = ranksel.RankSelection()
    population = [MagicMock(chrom.Chromosome) for _ in range(20)]
    assert 0 <= selection.get_index(population) < len(population)
