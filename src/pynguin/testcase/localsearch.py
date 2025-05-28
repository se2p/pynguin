#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
"""Provides the local search strategies."""
import abc
import logging
from abc import ABC

from pynguin.ga.chromosome import Chromosome
from pynguin.ga.testcasechromosome import TestCaseChromosome
from pynguin.ga.testsuitechromosome import TestSuiteChromosome


class LocalSearch(ABC):
    """An abstract class for local search."""

    _logger = logging.getLogger(__name__)

    @abc.abstractmethod
    def local_search(self, chromosome:Chromosome) -> None:
        """Executes local search on the chromosome."""

class TestCaseLocalSearch(LocalSearch, ABC):

    def local_search(self, chromosome:TestCaseChromosome) -> None:
        pass #TODO

class TestSuiteLocalSearch(LocalSearch, ABC):

    def local_search(self, chromosome:TestSuiteChromosome) -> None:
        pass #TODO
