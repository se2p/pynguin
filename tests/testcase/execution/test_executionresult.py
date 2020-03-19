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
