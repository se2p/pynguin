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
"""Provides an implementation for a test suite chromosome"""
from __future__ import annotations

import pynguin.testsuite.abstracttestsuitechromosome as atsc


# pylint:disable=too-many-instance-attributes
class TestSuiteChromosome(atsc.AbstractTestSuiteChromosome):
    """Provides an implementation for a test suite chromosome"""

    def clone(self) -> TestSuiteChromosome:
        chromosome = TestSuiteChromosome()

        for test in self._tests:
            chromosome.add_test(test.clone())

        chromosome._current_values = dict(self._current_values)
        chromosome._fitness_functions = list(self._fitness_functions)
        chromosome._changed = self._changed
        chromosome._test_case_factory = self._test_case_factory
        return chromosome
