#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
from unittest.mock import MagicMock

import pytest

import pynguin.ga.chromosome as chrom
import pynguin.ga.computations as ff

from pynguin.ga.chromosome import Chromosome


@pytest.fixture
def chromosome():
    class DummyChromosome(chrom.Chromosome):
        def mutate(self):
            pass  # pragma: no cover

        def size(self) -> int:
            return 0  # pragma: no cover

        def clone(self) -> Chromosome:
            pass  # pragma: no cover

        def cross_over(self, other: chrom.Chromosome, position1: int, position2: int) -> None:
            pass  # pragma: no cover

        def __hash__(self):
            return 0  # pragma: no cover

        def __eq__(self, other):
            return True  # pragma: no cover

        def length(self) -> int:
            return 0  # pragma: no cover

        def accept(self, visitor) -> None:
            pass  # pragma: no cover

    return DummyChromosome()


def test_has_changed_default(chromosome):
    assert chromosome.changed


def test_has_changed(chromosome):
    chromosome.changed = False
    assert not chromosome.changed


def test_get_fitness_functions(chromosome):
    func1 = MagicMock(ff.FitnessFunction)
    func1.is_maximisation_function.return_value = False
    func2 = MagicMock(ff.FitnessFunction)
    func2.is_maximisation_function.return_value = False
    chromosome.add_fitness_function(func1)
    chromosome.add_fitness_function(func2)
    assert chromosome.get_fitness_functions() == [func1, func2]
