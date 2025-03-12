#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
from unittest.mock import MagicMock

import pynguin.ga.chromosome as chrom
import pynguin.ga.operators.selection as sel


def test_random_selection():
    selection = sel.RandomSelection()
    population = [MagicMock(chrom.Selectable) for _ in range(20)]
    assert 0 <= selection.get_index(population) < len(population)
