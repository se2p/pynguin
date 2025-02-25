#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import pytest

from pynguin.ga.stoppingcondition import MaxTestExecutionsStoppingCondition


@pytest.fixture
def stopping_condition():
    return MaxTestExecutionsStoppingCondition(1000)


def test_set_get_limit(stopping_condition):
    stopping_condition.set_limit(42)
    assert stopping_condition.limit() == 42


def test_is_not_fulfilled(stopping_condition):
    stopping_condition.reset()
    assert not stopping_condition.is_fulfilled()


def test_is_fulfilled(stopping_condition):
    stopping_condition.set_limit(1)
    stopping_condition.before_remote_test_case_execution(None)
    stopping_condition.before_remote_test_case_execution(None)
    assert stopping_condition.is_fulfilled()
