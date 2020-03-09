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
"""Provides a whole-suite test generation algorithm similar to EvoSuite."""
import logging
from typing import Tuple
import pynguin.testsuite.testsuitechromosome as tsc

from pynguin.generation.algorithms.testgenerationstrategy import TestGenerationStrategy
from pynguin.testcase.execution.abstractexecutor import AbstractExecutor


# pylint: disable=too-few-public-methods
class WholeSuiteTestStrategy(TestGenerationStrategy):
    """Implements a whole-suite test generation algorithm similar to EvoSuite."""

    _logger = logging.getLogger(__name__)

    def __init__(self, executor: AbstractExecutor) -> None:
        super().__init__()
        self._executor = executor

    def generate_sequences(
        self,
    ) -> Tuple[tsc.TestSuiteChromosome, tsc.TestSuiteChromosome]:
        # TODO(fk): Mutation, evolve...
        return tsc.TestSuiteChromosome(), tsc.TestSuiteChromosome()
