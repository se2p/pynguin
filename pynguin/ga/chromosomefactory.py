#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Factory for chromosome used by the genetic algorithm."""
from abc import abstractmethod
from typing import Generic, TypeVar

import pynguin.ga.chromosome as chrom

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
