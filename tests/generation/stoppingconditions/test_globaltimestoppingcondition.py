#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
import time

import hypothesis.strategies as st
import pytest
from hypothesis import given

import pynguin.configuration as config
from pynguin.generation.stoppingconditions.globaltimestoppingcondition import (
    GlobalTimeStoppingCondition,
)
from pynguin.generation.stoppingconditions.stoppingcondition import StoppingCondition


@pytest.fixture
def stopping_condition():
    return GlobalTimeStoppingCondition()


def test_current_value(stopping_condition):
    stopping_condition.reset()
    start = time.time_ns()
    stopping_condition.current_value = start
    val = stopping_condition.current_value
    assert val >= 0


def test_limit(stopping_condition):
    assert stopping_condition.limit() == config.configuration.global_timeout


def test_is_not_fulfilled(stopping_condition):
    assert not stopping_condition.is_fulfilled()


def test_is_fulfilled(stopping_condition):
    config.configuration.global_timeout = 1
    stopping_condition.reset()
    stopping_condition.reset()
    time.sleep(1.05)
    assert stopping_condition.is_fulfilled()


def test_iterate(stopping_condition):
    stopping_condition.iterate()


def test_set_limit(stopping_condition):
    stopping_condition.set_limit(42)


@given(st.integers())
def test_current_value_of_base_class(x):
    class StoppingTestCondition(StoppingCondition):
        def limit(self) -> int:
            pass

        def is_fulfilled(self) -> bool:
            pass

        def reset(self) -> None:
            pass

        def set_limit(self, limit: int) -> None:
            pass

        def iterate(self) -> None:
            pass

    stopping_condition = StoppingTestCondition()
    stopping_condition.current_value = x
    assert stopping_condition.current_value == x
