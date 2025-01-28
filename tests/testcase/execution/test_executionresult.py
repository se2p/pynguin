#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import pytest

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


def test_get_first_position_of_ex(execution_result):
    execution_result.report_new_thrown_exception(5, Exception())
    execution_result.report_new_thrown_exception(3, Exception())
    assert execution_result.get_first_position_of_thrown_exception() == 3


def test_get_first_position_of_ex_none(execution_result):
    assert execution_result.get_first_position_of_thrown_exception() is None


def test_timeout(execution_result):
    assert execution_result.timeout


@pytest.mark.parametrize(
    "before,deleted,after",
    [
        ({0: "foo", 1: "bar"}, set(), {0: "foo", 1: "bar"}),
        ({0: "foo", 1: "bar"}, {0}, {0: "bar"}),
        ({0: "foo", 1: "bar", 5: "baz"}, {4}, {0: "foo", 1: "bar", 4: "baz"}),
    ],
)
def test_shift(before, deleted, after):
    assert ExecutionResult.shift_dict(before, deleted) == after
