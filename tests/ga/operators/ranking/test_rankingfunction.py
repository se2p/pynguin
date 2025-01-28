#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
from unittest.mock import MagicMock

import pytest

import pynguin.configuration as config
import pynguin.ga.chromosome as chrom

from pynguin.ga.operators.ranking import RankBasedPreferenceSorting
from pynguin.ga.operators.ranking import RankedFronts
from pynguin.ga.operators.ranking import RankingFunction


@pytest.fixture
def chromosome_mock():
    return MagicMock(chrom.Chromosome)


@pytest.fixture
def ranking_function() -> RankingFunction:
    return RankBasedPreferenceSorting()


@pytest.mark.parametrize(
    "fronts, rank, expected",
    [
        pytest.param(None, 0, []),
        pytest.param([], 1, []),
        pytest.param([[chromosome_mock]], 0, [chromosome_mock]),
    ],
)
def test_get_sub_front(fronts, rank, expected):
    ranked_fronts = RankedFronts(fronts=fronts)
    result = ranked_fronts.get_sub_front(rank)
    assert result == expected


def test_get_number_of_sub_fronts_when_none():
    ranked_fronts = RankedFronts(fronts=None)
    with pytest.raises(AssertionError):
        ranked_fronts.get_number_of_sub_fronts()


def test_get_number_of_sub_fronts(chromosome_mock):
    ranked_fronts = RankedFronts(fronts=[[chromosome_mock]])
    assert ranked_fronts.get_number_of_sub_fronts() == 1


def test_compute_raking_assignment_without_solutions(ranking_function):
    result = ranking_function.compute_ranking_assignment([], set())
    assert result == RankedFronts()


def test_compute_ranking_assignment(ranking_function):
    chromosome_1 = MagicMock(chrom.Chromosome)
    chromosome_2 = MagicMock(chrom.Chromosome)
    chromosome_3 = MagicMock(chrom.Chromosome)
    solutions = [chromosome_1, chromosome_2, chromosome_3]
    expected = RankedFronts(fronts=[[chromosome_1], [chromosome_2, chromosome_3]])

    def _get_zero_front(sol, _):
        return sol[:1]

    ranking_function._get_zero_front = _get_zero_front
    config.configuration.search_algorithm.population = 1

    result = ranking_function.compute_ranking_assignment(solutions, set())
    assert result == expected
