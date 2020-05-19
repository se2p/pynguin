# This file is part of Pynguin.
#
# Pynguin is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Pynguin is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Pynguin.  If not, see <https://www.gnu.org/licenses/>.
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
    assert stopping_condition.limit() == config.INSTANCE.global_timeout


def test_is_not_fulfilled(stopping_condition):
    assert not stopping_condition.is_fulfilled()


def test_is_fulfilled(stopping_condition):
    config.INSTANCE.global_timeout = 1
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
