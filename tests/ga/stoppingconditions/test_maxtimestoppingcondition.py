#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import time

from unittest import mock

import pytest

from pynguin.ga.stoppingcondition import MaxSearchTimeStoppingCondition


@pytest.fixture
def stopping_condition():
    return MaxSearchTimeStoppingCondition(600)


def test_current_value(stopping_condition):
    const = 1_000_000_000
    with mock.patch("time.time_ns") as time_mock:
        time_mock.return_value = 6 * const
        stopping_condition.before_search_start(5 * const)
        assert stopping_condition.current_value() == 1


def test_set_get_limit(stopping_condition):
    stopping_condition.set_limit(42)
    assert stopping_condition.limit() == 42


def test_is_not_fulfilled(stopping_condition):
    stopping_condition.reset()
    assert not stopping_condition.is_fulfilled()


def test_is_fulfilled(stopping_condition):
    stopping_condition.reset()
    stopping_condition.set_limit(0)
    time.sleep(0.05)
    assert stopping_condition.is_fulfilled()
