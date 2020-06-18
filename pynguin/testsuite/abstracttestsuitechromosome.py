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
from typing import Any, List, Optional

import pynguin.configuration as config
import pynguin.ga.chromosome as chrom
import pynguin.ga.testcasefactory as tcf
import pynguin.testcase.testcase as tc
from pynguin.utils import randomness


class AbstractTestSuiteChromosome(chrom.Chromosome, metaclass=ABCMeta):
    """An abstract base class for a test suite chromosome"""

    def __init__(self, test_case_factory: Optional[tcf.TestCaseFactory] = None):
        super().__init__()
        self._tests: List[tc.TestCase] = []
        self._test_case_factory = test_case_factory

    def add_test(self, test: tc.TestCase) -> None:
        """Adds a test case to the test suite.

        Args:
            test: the test case to be added
        """
        self._tests.append(test)
        self.set_changed(True)

    def delete_test(self, test: tc.TestCase) -> None:
        """Delete a test case from the test suite.

        Args:
            test: the test to delete
        """
        try:
            self._tests.remove(test)
            self.set_changed(True)
        except ValueError:
            pass

    def add_tests(self, tests: List[tc.TestCase]) -> None:
        """Adds a list of test cases to the test suite.

        Args:
            tests: A list of test cases to add
        """
        self._tests.extend(tests)
        if tests:
            self.set_changed(True)

    @abstractmethod
    def clone(self) -> chrom.Chromosome:
        """Clones the chromosome.

        Returns:
            The clone of the chromosome  # noqa: DAR202
        """

    def get_test_chromosome(self, index: int) -> tc.TestCase:
        """Provides the test chromosome at a certain index.

        Args:
            index: the index to select

        Returns:
            The test case at the given index
        """
        return self._tests[index]

    @property
    def test_chromosomes(self) -> List[tc.TestCase]:
        """Provides all test chromosomes.

        Returns:
            The list of all test cases
        """
        return self._tests

    def set_test_chromosome(self, index: int, test: tc.TestCase) -> None:
        """Sets a test chromosome at a certain index.

        Args:
            index: the index to set the chromosome
            test: the test case to set
        """
        self._tests[index] = test
        self.set_changed(True)

    @property
    def total_length_of_test_cases(self) -> int:
        """Provides the sum of the lengths of the test cases.

        Returns:
            The total length of the test cases
        """
        return sum([test.size() for test in self._tests])

    def size(self) -> int:
        """Provides the size of the chromosome, i.e., its number of test cases.

        Returns:
            The size of the chromosome
        """
        return len(self._tests)

    def cross_over(
        self, other: chrom.Chromosome, position1: int, position2: int
    ) -> None:
        """Performs the crossover with another chromosome.

        Keep tests up to position1. Append copies of tests from other from position2
        onwards.

        Args:
            other: the other chromosome
            position1: the position in the first chromosome
            position2: the position in the second chromosome

        Raises:
            RuntimeError: If other is not an instance of AbstractTestSuiteChromosome
        """
        if not isinstance(other, AbstractTestSuiteChromosome):
            raise RuntimeError("Cannot perform crossover with " + str(type(other)))

        self._tests = self._tests[:position1] + [
            test.clone() for test in other._tests[position2:]
        ]
        self.set_changed(True)

    def mutate(self) -> None:
        """Apply mutation at test suite level."""
        assert self._test_case_factory, "Can only mutate with test case factory."
        changed = False

        # Mutate existing test cases.
        for test in self._tests:
            if randomness.next_float() < 1.0 / self.size():
                test.mutate()
                if test.has_changed():
                    changed = True

        # Randomly add new test cases.
        alpha = config.INSTANCE.test_insertion_probability
        exponent = 1
        while (
            randomness.next_float() <= pow(alpha, exponent)
            and self.size() < config.INSTANCE.max_size
        ):
            self.add_test(self._test_case_factory.get_test_case())
            exponent += 1
            changed = True

        # Remove any tests that have no more statements left.
        self._tests = [t for t in self._tests if t.size() > 0]

        if changed:
            self.set_changed(True)

    def __eq__(self, other: Any) -> bool:
        if self is other:
            return True
        if not isinstance(other, AbstractTestSuiteChromosome):
            return False
        if self.size() != other.size():
            return False
        for test, other_test in zip(self._tests, other._tests):
            if test != other_test:
                return False
        return True

    def __hash__(self) -> int:
        return 31 + sum([17 * hash(t) for t in self._tests])
