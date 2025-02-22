#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT

#  This file is part of Pynguin.
#
#
#  SPDX-License-Identifier: MIT
#
from unittest.mock import MagicMock

import pytest

import pynguin.ga.chromosome as chrom
import pynguin.ga.computations as ff
import pynguin.ga.operators.comparator as dc

from pynguin.utils.orderedset import OrderedSet


@pytest.fixture
def comparator():
    return dc.DominanceComparator()


def test_constructor_no_parameter(comparator):
    assert comparator._objectives is None


def test_constructor_goal_parameter():
    goal = MagicMock(ff.FitnessFunction)
    comparator = dc.DominanceComparator(goal=goal)
    assert comparator._objectives == OrderedSet([goal])


def test_constructor_goals_parameter():
    goals = {MagicMock(ff.FitnessFunction), MagicMock(ff.FitnessFunction)}
    comparator = dc.DominanceComparator(goals=goals)
    assert comparator._objectives == goals


def test_compare_chromosome_1_none(comparator):
    assert comparator.compare(None, MagicMock(chrom.Chromosome)) == 1


def test_compare_chromosome_2_none(comparator):
    assert comparator.compare(MagicMock(chrom.Chromosome), None) == -1
