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
"""Provides an abstract base class for a test suite chromosome."""
from abc import ABCMeta
from typing import List

import pynguin.testcase.testcase as tc
import pynguin.ga.chromosome as chrom


class AbstractTestSuiteChromosome(chrom.Chromosome, metaclass=ABCMeta):
    """An abstract base class for a test suite chromosome"""

    def __init__(self):
        super().__init__()
        self._tests: List[tc.TestCase] = []

    @property
    def total_length_of_test_cases(self) -> int:
        """Provides the sum of the lengths of the test cases."""
        return sum([test.size() for test in self._tests])

    @property
    def size(self) -> int:
        """Provides the size of the chromosome, i.e., its number of test cases."""
        return len(self._tests)
