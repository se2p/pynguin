#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2023 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
from unittest.mock import MagicMock

import pynguin.ga.operators.selection.selection as sel
import pynguin.ga.testsuitechromosome as tsc

from pynguin.ga.operators.selection.selection import T
from pynguin.utils import randomness


class PseudoSelection(sel.SelectionFunction):
    def get_index(self, population: list[T]) -> int:
        return randomness.next_int(0, len(population))


def test_select():
    func = PseudoSelection()
    population = [MagicMock(tsc.TestSuiteChromosome) for i in range(10)]
    assert len(func.select(population, 5)) == 5


def test_maximize():
    func = PseudoSelection()
    func.maximize = True
    assert func.maximize
