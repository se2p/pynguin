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
from typing import List
from unittest.mock import MagicMock

import pynguin.testsuite.testsuitechromosome as tsc
import pynguin.ga.operators.selection.selection as sel
from pynguin.ga.operators.selection.selection import T
from pynguin.utils import randomness


class PseudoSelection(sel.SelectionFunction):
    def get_index(self, population: List[T]) -> int:
        return randomness.next_int(0, len(population))


def test_select():
    func = PseudoSelection()
    population = [MagicMock(tsc.TestSuiteChromosome) for i in range(10)]
    assert len(func.select(population, 5)) == 5


def test_maximize():
    func = PseudoSelection()
    func.maximize = True
    assert func.maximize
