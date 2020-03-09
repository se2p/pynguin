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


class TestSuiteChromosome(atsc.AbstractTestSuiteChromosome):
    """Provides an implementation for a test suite chromosome"""

    def clone(self) -> TestSuiteChromosome:
        chromosome = TestSuiteChromosome()

        for test in self._tests:
            chromosome.add_test(test.clone())

        chromosome.fitness_values = self.fitness_values
        chromosome.previous_fitness_values = self.previous_fitness_values
        chromosome.changed = self.changed
        chromosome.coverage_values = self.coverage_values
        chromosome.nums_not_covered_goals = self.nums_not_covered_goals
        chromosome.nums_covered_goals = self.nums_covered_goals
        chromosome.number_of_evaluations = self.number_of_evaluations

        return chromosome
