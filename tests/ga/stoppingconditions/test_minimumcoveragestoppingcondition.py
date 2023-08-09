#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2023 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import pytest

from pynguin.ga.stoppingcondition import MinimumCoverageStoppingCondition


@pytest.fixture
def stopping_condition():
    return MinimumCoverageStoppingCondition(0.8, 10)


def test_set_get_limit(stopping_condition):
    stopping_condition.set_limit(0.5)
    assert stopping_condition.limit() == 0.5


def test_is_not_fulfilled(stopping_condition):
    assert not stopping_condition.is_fulfilled()


def test_reset(stopping_condition):
    stopping_condition.after_search_iteration(None)
    stopping_condition.reset()
    assert stopping_condition.current_value() == 0.0


def test_before_search_start(stopping_condition):
    stopping_condition.after_search_iteration(None)
    assert stopping_condition.current_value() > 0.1
    stopping_condition.before_search_start(None)
    assert stopping_condition.current_value() == 0.0


def test_is_fulfilled(stopping_condition):
    stopping_condition.set_limit(0.1)
    stopping_condition.after_search_iteration(None)
    stopping_condition.after_search_iteration(None)
    assert stopping_condition.is_fulfilled()
