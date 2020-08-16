#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
import time

from pynguin.testcase.execution.executionresult import ExecutionResult


def test_default_values():
    result = ExecutionResult()
    assert not result.has_test_exceptions()


def test_report_new_thrown_exception():
    result = ExecutionResult()
    result.report_new_thrown_exception(0, Exception())
    assert result.has_test_exceptions()


def test_exceptions():
    result = ExecutionResult()
    ex = Exception()
    result.report_new_thrown_exception(0, ex)
    assert result.exceptions[0] == ex


def test_fitness_setter():
    result = ExecutionResult()
    result.fitness = 5.0
    assert result.fitness == 5.0


def test_time_stamp():
    current = time.time_ns()
    result = ExecutionResult()
    assert current <= result.time_stamp


def test_get_first_position_of_ex():
    result = ExecutionResult()
    result.report_new_thrown_exception(5, Exception())
    result.report_new_thrown_exception(3, Exception())
    assert result.get_first_position_of_thrown_exception() == 3


def test_get_first_position_of_ex_none():
    result = ExecutionResult()
    assert result.get_first_position_of_thrown_exception() is None
