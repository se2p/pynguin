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
from abc import ABCMeta, abstractmethod
from typing import List, Any

import pynguin.testcase.testcase as tc
import pynguin.ga.chromosome as chrom


class AbstractTestSuiteChromosome(chrom.Chromosome, metaclass=ABCMeta):
    """An abstract base class for a test suite chromosome"""

    def __init__(self):
        super().__init__()
        self._tests: List[tc.TestCase] = []

    def add_test(self, test: tc.TestCase) -> None:
        """Adds a test case to the test suite"""
        self._tests.append(test)
        self.set_changed(True)

    def delete_test(self, test: tc.TestCase) -> None:
        """Delete a test case from the test suite"""
        try:
            self._tests.remove(test)
            self.set_changed(True)
        except ValueError:
            pass

    def add_tests(self, tests: List[tc.TestCase]) -> None:
        """Adds a list of test cases to the test suite"""
        self._tests.extend(tests)
        if tests:
            self.set_changed(True)

    @abstractmethod
    def clone(self) -> chrom.Chromosome:
        """Clones the chromosome"""

    def get_test_chromosome(self, index: int) -> tc.TestCase:
        """Provides the test chromosome at a certain index"""
        return self._tests[index]

    @property
    def test_chromosomes(self) -> List[tc.TestCase]:
        """Provides all test chromosomes"""
        return self._tests

    def set_test_chromosome(self, index: int, test: tc.TestCase) -> None:
        """Sets a test chromosome at a certain index"""
        self._tests[index] = test
        self.set_changed(True)

    @property
    def total_length_of_test_cases(self) -> int:
        """Provides the sum of the lengths of the test cases."""
        return sum([test.size() for test in self._tests])

    @property
    def size(self) -> int:
        """Provides the size of the chromosome, i.e., its number of test cases."""
        return len(self._tests)

    def __eq__(self, other: Any) -> bool:
        if self is other:
            return True
        if not isinstance(other, AbstractTestSuiteChromosome):
            return False
        if self.size != other.size:
            return False
        for test, other_test in zip(self._tests, other._tests):
            if test != other_test:
                return False
        return True

    def __hash__(self) -> int:
        return 31 + sum([17 * hash(t) for t in self._tests])
