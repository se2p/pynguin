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
"""Factory for chromosome used by the genetic algorithm."""
from abc import abstractmethod
from typing import Generic, TypeVar

import pynguin.configuration as config
import pynguin.ga.chromosome as chrom
import pynguin.ga.testcasefactory as tcf
import pynguin.testsuite.testsuitechromosome as tsc
from pynguin.utils import randomness

T = TypeVar("T", bound=chrom.Chromosome)  # pylint: disable=invalid-name


# pylint: disable=too-few-public-methods
class ChromosomeFactory(Generic[T]):
    """A factory that provides new chromosomes."""

    @abstractmethod
    def get_chromosome(self) -> T:
        """Create a new chromosome.

        Returns:
            A new chromosome  # noqa: DAR202
        """


class TestSuiteChromosomeFactory(ChromosomeFactory[tsc.TestSuiteChromosome]):
    """A factory that provides new test suite chromosomes of random length."""

    def __init__(self, test_case_factory: tcf.TestCaseFactory):
        """Instantiates a new factory

        Args:
            test_case_factory: The internal test case factory
        """
        self._test_case_factory = test_case_factory

    def get_chromosome(self) -> tsc.TestSuiteChromosome:
        chromosome = tsc.TestSuiteChromosome(self._test_case_factory)
        num_tests = randomness.next_int(
            config.INSTANCE.min_initial_tests, config.INSTANCE.max_initial_tests + 1
        )

        for _ in range(num_tests):
            chromosome.add_test(self._test_case_factory.get_test_case())

        return chromosome
