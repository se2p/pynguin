#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
from unittest.mock import MagicMock

import pytest

import pynguin.ga.chromosome as chrom
import pynguin.ga.operators.comparator as pc


@pytest.fixture
def comparator():
    return pc.PreferenceSortingComparator(MagicMock())


def test_compare_chromosome_1_none(comparator):
    assert comparator.compare(None, MagicMock(chrom.Chromosome)) == 1


def test_compare_chromosome_2_none(comparator):
    assert comparator.compare(MagicMock(chrom.Chromosome), None) == -1
