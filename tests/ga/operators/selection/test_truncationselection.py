#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
from unittest.mock import MagicMock

import pynguin.ga.chromosome as chrom
import pynguin.ga.operators.selection as sel


def test_truncation_selection_index_is_the_fittest():
    selection = sel.TruncationSelection()
    population = [MagicMock(chrom.Selectable) for _ in range(20)]
    assert selection.get_index(population) == 0


def test_truncation_selection_selects_the_first_individuals_without_replacement():
    selection = sel.TruncationSelection()
    population = [MagicMock(chrom.Selectable) for _ in range(5)]
    assert selection.select(population, 3) == population[:3]


def test_truncation_selection_selects_at_most_the_whole_population():
    selection = sel.TruncationSelection()
    population = [MagicMock(chrom.Selectable) for _ in range(2)]
    assert selection.select(population, 5) == population
