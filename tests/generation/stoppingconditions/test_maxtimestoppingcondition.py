#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
import time

import pytest

from pynguin.generation.stoppingconditions.maxtimestoppingcondition import (
    MaxTimeStoppingCondition,
)


@pytest.fixture
def stopping_condition():
    return MaxTimeStoppingCondition()


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


def test_iterate(stopping_condition):
    stopping_condition.iterate()
