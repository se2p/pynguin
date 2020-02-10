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
"""Provides a test suite."""
from __future__ import annotations
from typing import List

import pynguin.testcase.testcase as tc


class TestSuite:
    """A test suite that is used for the genetic algorithm."""

    def __init__(self):
        self._test_cases: List[tc.TestCase] = []

    def total_length_of_test_cases(self) -> int:
        """The the total length of all contained test cases."""
        length = 0
        for test_case in self._test_cases:
            length += test_case.size()
        return length

    def size(self):
        """The size of this test suite."""
        return len(self._test_cases)

    @property
    def test_cases(self) -> List[tc.TestCase]:
        """Provide the test cases of this suite."""
        return self._test_cases

    @test_cases.setter
    def test_cases(self, value: List[tc.TestCase]):
        """Set the test cases of this suite."""
        self._test_cases = value

    def clone(self) -> TestSuite:
        """Create a deep clone of this suite."""
        cloned = TestSuite()
        for test_case in self._test_cases:
            cloned._test_cases.append(test_case.clone())
        return cloned
