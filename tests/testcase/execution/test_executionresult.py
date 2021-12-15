#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
from unittest.mock import MagicMock

import pytest

import pynguin.assertion.statetrace as ot
from pynguin.testcase.execution import ExecutionResult


@pytest.fixture
def execution_result():
    return ExecutionResult(timeout=True)


def test_default_values(execution_result):
    assert not execution_result.has_test_exceptions()


def test_report_new_thrown_exception(execution_result):
    execution_result.report_new_thrown_exception(0, Exception())
    assert execution_result.has_test_exceptions()


def test_exceptions(execution_result):
    ex = Exception()
    execution_result.report_new_thrown_exception(0, ex)
    assert execution_result.exceptions[0] == ex


def test_fitness_setter(execution_result):
    execution_result.fitness = 5.0
    assert execution_result.fitness == 5.0


def test_get_first_position_of_ex(execution_result):
    execution_result.report_new_thrown_exception(5, Exception())
    execution_result.report_new_thrown_exception(3, Exception())
    assert execution_result.get_first_position_of_thrown_exception() == 3


def test_get_first_position_of_ex_none(execution_result):
    assert execution_result.get_first_position_of_thrown_exception() is None


def test_timeout(execution_result):
    assert execution_result.timeout


def test_output_traces(execution_result):
    trace = MagicMock(ot.StateTrace)
    execution_result.add_output_trace(str, trace)
    assert execution_result.output_traces == {str: trace}
