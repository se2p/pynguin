#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2023 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import pytest

from pynguin.generation.stoppingconditions.stoppingcondition import (
    MaxStatementExecutionsStoppingCondition,
)


@pytest.fixture
def stopping_condition():
    return MaxStatementExecutionsStoppingCondition(10000)


def test_current_value(stopping_condition):
    assert stopping_condition.current_value() == 0


def test_current_value_reset(stopping_condition):
    stopping_condition.before_statement_execution(None, None, None)
    stopping_condition.reset()
    assert stopping_condition.current_value() == 0


def test_before_search_start(stopping_condition):
    stopping_condition.before_statement_execution(None, None, None)
    stopping_condition.before_search_start(None)
    assert stopping_condition.current_value() == 0


def test_set_get_limit(stopping_condition):
    stopping_condition.set_limit(42)
    assert stopping_condition.limit() == 42


def test_is_not_fulfilled(stopping_condition):
    assert not stopping_condition.is_fulfilled()


def test_is_fulfilled(stopping_condition):
    stopping_condition.set_limit(3)
    stopping_condition.before_statement_execution(None, None, None)
    stopping_condition.before_statement_execution(None, None, None)
    stopping_condition.before_statement_execution(None, None, None)
    assert stopping_condition.is_fulfilled()
