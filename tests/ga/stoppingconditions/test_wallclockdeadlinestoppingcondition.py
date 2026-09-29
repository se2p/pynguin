#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
from unittest import mock

import pytest

from pynguin.ga.stoppingcondition import WallClockDeadlineStoppingCondition

_NS = 1_000_000_000


@pytest.fixture
def stopping_condition():
    with mock.patch("time.time_ns") as time_mock:
        time_mock.return_value = 100 * _NS
        yield WallClockDeadlineStoppingCondition(110 * _NS)


def test_is_not_fulfilled_before_deadline(stopping_condition):
    with mock.patch("time.time_ns") as time_mock:
        time_mock.return_value = 109 * _NS
        assert not stopping_condition.is_fulfilled()


def test_is_fulfilled_at_deadline(stopping_condition):
    with mock.patch("time.time_ns") as time_mock:
        time_mock.return_value = 110 * _NS
        assert stopping_condition.is_fulfilled()


def test_is_fulfilled_after_deadline(stopping_condition):
    with mock.patch("time.time_ns") as time_mock:
        time_mock.return_value = 111 * _NS
        assert stopping_condition.is_fulfilled()


def test_before_search_start_does_not_reset_deadline(stopping_condition):
    """Verifies the deadline stays fixed across islands.

    Unlike every other StoppingCondition, before_search_start() must not move it.
    """
    with mock.patch("time.time_ns") as time_mock:
        time_mock.return_value = 109 * _NS
        stopping_condition.before_search_start(time_mock.return_value)
        assert not stopping_condition.is_fulfilled()

        time_mock.return_value = 110 * _NS
        assert stopping_condition.is_fulfilled()


def test_reset_does_not_move_deadline(stopping_condition):
    stopping_condition.reset()
    with mock.patch("time.time_ns") as time_mock:
        time_mock.return_value = 110 * _NS
        assert stopping_condition.is_fulfilled()


def test_set_limit_moves_deadline_relative_to_now():
    with mock.patch("time.time_ns") as time_mock:
        time_mock.return_value = 200 * _NS
        stopping_condition = WallClockDeadlineStoppingCondition(210 * _NS)
        stopping_condition.set_limit(5)
        time_mock.return_value = 204 * _NS
        assert not stopping_condition.is_fulfilled()
        time_mock.return_value = 205 * _NS
        assert stopping_condition.is_fulfilled()
