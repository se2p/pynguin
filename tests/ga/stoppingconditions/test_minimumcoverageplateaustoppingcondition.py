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

from pynguin.ga.stoppingcondition import MinimumCoveragePlateauStoppingCondition
from pynguin.ga.stoppingcondition import StoppingCondition


@pytest.fixture
def stopping_condition() -> StoppingCondition:
    return MinimumCoveragePlateauStoppingCondition(50, 1)


@pytest.fixture
def individual_1() -> tsc.TestSuiteChromosome:
    chromosome = MagicMock(tsc.TestSuiteChromosome)
    chromosome.get_coverage.return_value = 0.40
    return chromosome


@pytest.fixture
def individual_2() -> tsc.TestSuiteChromosome:
    chromosome = MagicMock(tsc.TestSuiteChromosome)
    chromosome.get_coverage.return_value = 0.60
    return chromosome


@pytest.fixture
def individual_3() -> tsc.TestSuiteChromosome:
    chromosome = MagicMock(tsc.TestSuiteChromosome)
    chromosome.get_coverage.return_value = 0.60
    return chromosome


def test_current_value(stopping_condition):
    assert stopping_condition.current_value() == 0


def test_limit(stopping_condition):
    assert stopping_condition.limit() == 50


def test_is_not_fulfilled(stopping_condition, individual_1):
    stopping_condition.after_search_iteration(individual_1)
    assert not stopping_condition.is_fulfilled()


def test_is_fulfilled(stopping_condition, individual_2, individual_3):
    stopping_condition.after_search_iteration(individual_2)
    stopping_condition.after_search_iteration(individual_3)
    assert stopping_condition.is_fulfilled()


def test_is_not_fulfilled_different(stopping_condition, individual_1, individual_2):
    stopping_condition.after_search_iteration(individual_1)
    stopping_condition.after_search_iteration(individual_2)
    assert not stopping_condition.is_fulfilled()


def test_reset(stopping_condition, individual_1):
    stopping_condition.after_search_iteration(individual_1)
    assert stopping_condition.current_value() == 40
    stopping_condition.reset()
    assert stopping_condition.current_value() == 0


@given(value=st.integers())
def test_set_limit(value):
    stopping_condition = MinimumCoveragePlateauStoppingCondition(1, 1)
    stopping_condition.set_limit(value)
    assert stopping_condition.limit() == value


def test_before_search_start(stopping_condition, individual_1):
    stopping_condition.after_search_iteration(individual_1)
    stopping_condition.before_search_start(0)
    assert stopping_condition.current_value() == 0
