#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
from unittest.mock import MagicMock

import pytest

import pynguin.ga.chromosome as chrom
from pynguin.generation.algorithms.testgenerationstrategy import TestGenerationStrategy
from pynguin.generation.stoppingconditions.stoppingcondition import StoppingCondition


class _TestGenerationStrategy(TestGenerationStrategy):
    def __init__(self):
        super().__init__()

    def generate_tests(self) -> chrom.Chromosome:
        raise NotImplementedError(
            "This class is not intended for usage but only for testing"
        )


@pytest.fixture
def algorithm():
    return _TestGenerationStrategy()


def test_is_fulfilled(algorithm):
    stopping_condition = MagicMock(StoppingCondition)
    stopping_condition.is_fulfilled.return_value = True
    assert algorithm.is_fulfilled(stopping_condition)


def test_is_not_fulfilled(algorithm):
    stopping_condition = MagicMock(StoppingCondition)
    stopping_condition.is_fulfilled.return_value = False
    assert not algorithm.is_fulfilled(stopping_condition)
