#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
from unittest.mock import MagicMock

import hypothesis.strategies as st
import pytest

from hypothesis import given

import pynguin.ga.testsuitechromosome as tsc

from pynguin.ga.stoppingcondition import CoveragePlateauStoppingCondition


@pytest.fixture
def stopping_condition():
    return CoveragePlateauStoppingCondition(50)


@pytest.fixture
def individual() -> tsc.TestSuiteChromosome:
    chromosome = MagicMock(tsc.TestSuiteChromosome)
    chromosome.get_coverage.return_value = 0.60
    return chromosome


def test_current_value(stopping_condition):
    assert stopping_condition.current_value() == 0


def test_limit(stopping_condition):
    assert stopping_condition.limit() == 50


def test_is_fulfilled(stopping_condition, individual):
    stopping_condition.set_limit(1)
    stopping_condition.after_search_iteration(individual)
    assert not stopping_condition.is_fulfilled()
    stopping_condition.after_search_iteration(individual)
    assert stopping_condition.is_fulfilled()


def test_reset(stopping_condition, individual):
    stopping_condition.after_search_iteration(individual)
    stopping_condition.after_search_iteration(individual)
    assert stopping_condition.current_value() == 1
    stopping_condition.reset()
    assert stopping_condition.current_value() == 0


@given(value=st.integers())
def test_set_limit(value):
    stopping_condition = CoveragePlateauStoppingCondition(1)
    stopping_condition.set_limit(value)
    assert stopping_condition.limit() == value


def test_before_search_start(stopping_condition, individual):
    stopping_condition.after_search_iteration(individual)
    stopping_condition.before_search_start(0)
    assert stopping_condition.current_value() == 0
