#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
from typing import List, Set
from unittest.mock import MagicMock

import pytest

import pynguin.ga.chromosome as chrom
import pynguin.ga.fitnessfunction as ff
from pynguin.generation.algorithms.mosa.archive import Archive


@pytest.fixture
def zero_fitness_function() -> ff.FitnessFunction:
    fitness_function = MagicMock(ff.FitnessFunction)
    result = ff.FitnessValues(fitness=0.0, coverage=0.0)
    fitness_function.compute_fitness_values.return_value = result
    return fitness_function


@pytest.fixture
def non_zero_fitness_function() -> ff.FitnessFunction:
    fitness_function = MagicMock(ff.FitnessFunction)
    result = ff.FitnessValues(fitness=42.0, coverage=0.0)
    fitness_function.compute_fitness_values.return_value = result
    return fitness_function


@pytest.fixture
def objectives(
    zero_fitness_function, non_zero_fitness_function
) -> Set[ff.FitnessFunction]:
    return {zero_fitness_function, non_zero_fitness_function}


@pytest.fixture
def short_chromosome() -> chrom.Chromosome:
    chromosome = MagicMock(chrom.Chromosome)
    chromosome.size.return_value = 2
    chromosome.get_fitness_for.return_value = 0.0
    return chromosome


@pytest.fixture
def long_chromosome() -> chrom.Chromosome:
    chromosome = MagicMock(chrom.Chromosome)
    chromosome.size.return_value = 42
    chromosome.get_fitness_for.return_value = 42.0
    return chromosome


@pytest.fixture
def chromosomes(short_chromosome, long_chromosome) -> List[chrom.Chromosome]:
    return [short_chromosome, long_chromosome]


def test_uncovered_goals(objectives):
    archive = Archive(objectives)
    assert archive.uncovered_goals == objectives


def test_reset(objectives):
    archive = Archive(objectives)
    archive.reset()
    assert archive.uncovered_goals == objectives
    assert archive.covered_goals == set()
    assert archive.solutions == set()


def test_update_solution(objectives, chromosomes):
    archive = Archive(objectives)
    archive.update(chromosomes)
    solution = archive.solutions
    assert solution == {chromosomes[0]}
