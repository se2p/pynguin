#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provide various crossover functions for genetic algorithms."""

from __future__ import annotations

from abc import abstractmethod
from math import floor
from typing import TYPE_CHECKING, Generic, TypeVar

import pynguin.configuration as config
import pynguin.ga.chromosome as chrom
from pynguin.utils import randomness

if TYPE_CHECKING:
    from pynguin.ga.testcasechromosome import TestCaseChromosome
    from pynguin.ga.testsuitechromosome import TestSuiteChromosome

T = TypeVar("T", bound=chrom.Chromosome)


def splice_test_case_chromosomes(
    parent: TestCaseChromosome,
    other: TestCaseChromosome,
    position1: int,
    position2: int,
) -> None:
    """Perform crossover on TestCaseChromosome.

    Args:
        parent: The parent chromosome to mutate in place
        other: The other parent chromosome
        position1: Crossover split point for parent
        position2: Crossover split point for other
    """
    assert parent._test_factory is not None, "Crossover requires a test factory."  # noqa: SLF001

    offspring_test_case = parent.test_case.clone()
    # Keep only the first `position1` statements of this parent.
    if offspring_test_case.size() > position1:
        offspring_test_case.remove_statements_batch(
            set(range(position1, offspring_test_case.size()))
        )

    offspring_test_case.append_test_case_from(other.test_case, position2)

    if offspring_test_case.size() < config.configuration.search_algorithm.chromosome_length:
        parent._test_case = offspring_test_case  # noqa: SLF001
        parent.changed = True


def splice_test_suite_chromosomes(
    parent: TestSuiteChromosome,
    other: TestSuiteChromosome,
    position1: int,
    position2: int,
) -> None:
    """Perform crossover on TestSuiteChromosome.

    Args:
        parent: The parent chromosome to mutate in place
        other: The other parent chromosome
        position1: Crossover split point for parent
        position2: Crossover split point for other
    """
    parent.test_case_chromosomes = parent.test_case_chromosomes[:position1] + [
        test.clone() for test in other.test_case_chromosomes[position2:]
    ]
    parent.changed = True


class CrossOverFunction(Generic[T]):
    """Cross over two individuals."""

    @abstractmethod
    def cross_over(self, parent_1: T, parent_2: T) -> None:
        """Perform a crossover between the two parents.

        Args:
            parent_1: The first parent chromosome
            parent_2: The second parent chromosome
        """


class SinglePointRelativeCrossOver(CrossOverFunction[T]):
    """Performs a single-point relative crossover of the two parents.

    The splitting point is not an absolute but a relative value (e.g., at position 70%
    of n). For example, if n1=10 and n2=20 and the splitting point is 70%, we would have
    position 7 in the first and 14 in the second.

    Therefore, the offspring d has n<=max(n1, n2)
    """

    def cross_over(self, parent_1: T, parent_2: T) -> None:  # noqa: D102
        if parent_1.size() < 2 or parent_2.size() < 2:
            return

        split_point = randomness.next_float()
        pos_1 = floor((parent_1.size() - 1) * split_point) + 1
        pos_2 = floor((parent_2.size() - 1) * split_point) + 1
        clone_1 = parent_1.clone()
        clone_2 = parent_2.clone()
        parent_1.cross_over(clone_2, pos_1, pos_2)
        parent_2.cross_over(clone_1, pos_2, pos_1)
