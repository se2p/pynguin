#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
from unittest.mock import MagicMock

import pytest

import pynguin.ga.chromosome as chrom
from pynguin.ga.operators.ranking.rankingfunction import RankedFronts


@pytest.fixture
def chromosome_mock():
    return MagicMock(chrom.Chromosome)


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
