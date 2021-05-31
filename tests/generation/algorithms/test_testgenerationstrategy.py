#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
from unittest.mock import MagicMock

import pytest

import pynguin.configuration as config
import pynguin.ga.chromosome as chrom
import pynguin.testcase.statements.statement as stmt
import pynguin.testcase.testcase as tc
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


def test_not_has_type_violations(algorithm):
    assert not algorithm.has_type_violations([])


def test_has_type_violations(algorithm):
    assert algorithm.has_type_violations([Exception(), TypeError(), AttributeError()])


def test_purge_test_cases_without_threshold(algorithm, test_case_mock):
    config.configuration.random.counter_threshold = 0
    purged, remaining = algorithm.purge_test_cases([test_case_mock])
    assert purged == []
    assert remaining == [test_case_mock]


def test_purge_test_cases(algorithm):
    config.configuration.random.counter_threshold = 1
    tc_1 = MagicMock(tc.TestCase)
    tc_1.statements = [MagicMock(stmt.Statement)]
    tc_2 = MagicMock(tc.TestCase)
    tc_2.statements = [MagicMock(stmt.Statement), MagicMock(stmt.Statement)]
    purged, remaining = algorithm.purge_test_cases([tc_1, tc_2])
    assert purged == [tc_2]
    assert remaining == [tc_1]


def test_is_fulfilled(algorithm):
    stopping_condition = MagicMock(StoppingCondition)
    stopping_condition.is_fulfilled.return_value = True
    assert algorithm.is_fulfilled(stopping_condition)


def test_is_not_fulfilled(algorithm):
    stopping_condition = MagicMock(StoppingCondition)
    stopping_condition.is_fulfilled.return_value = False
    assert not algorithm.is_fulfilled(stopping_condition)
