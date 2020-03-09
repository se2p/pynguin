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
"""Integration tests for the executor."""
import pytest

import pynguin.configuration as config
import pynguin.testcase.defaulttestcase as dtc
import pynguin.testcase.statements.parametrizedstatements as param_stmt
import pynguin.testcase.statements.primitivestatements as prim_stmt
import pynguin.testsuite.testsuitechromosome as tsc
from pynguin.testcase.execution.testcaseexecutor import TestCaseExecutor


def test_simple_execution():
    config.INSTANCE.module_name = "tests.fixtures.accessibles.accessible"
    test_case = dtc.DefaultTestCase()
    test_case.add_statement(prim_stmt.IntPrimitiveStatement(test_case, 5))
    executor = TestCaseExecutor()
    assert not executor.execute(test_case).has_test_exceptions()


def test_illegal_call(method_mock):
    config.INSTANCE.module_name = "tests.fixtures.accessibles.accessible"
    test_case = dtc.DefaultTestCase()
    int_stmt = prim_stmt.IntPrimitiveStatement(test_case, 5)
    method_stmt = param_stmt.MethodStatement(
        test_case, method_mock, int_stmt.return_value
    )
    test_case.add_statement(int_stmt)
    test_case.add_statement(method_stmt)
    executor = TestCaseExecutor()
    result = executor.execute(test_case)
    assert result.has_test_exceptions()


def test_no_exceptions(short_test_case):
    config.INSTANCE.module_name = "tests.fixtures.accessibles.accessible"
    executor = TestCaseExecutor()
    result = executor.execute(short_test_case)
    assert not result.has_test_exceptions()


def test_create_object_only_import(constructor_mock):
    config.INSTANCE.module_name = "tests.fixtures.accessibles.accessible"
    test_case = dtc.DefaultTestCase()
    executor = TestCaseExecutor()
    result = executor.execute(test_case)
    assert result.branch_coverage == 50.0


def test_create_object_with_coverage(short_test_case):
    config.INSTANCE.module_name = "tests.fixtures.accessibles.accessible"
    executor = TestCaseExecutor()
    result = executor.execute(short_test_case)
    assert result.branch_coverage == 75.0


def test_execute_test_suite(short_test_case):
    config.INSTANCE.module_name = "tests.fixtures.accessibles.accessible"
    executor = TestCaseExecutor()
    test_suite = tsc.TestSuiteChromosome()
    test_suite.add_test(short_test_case)
    result = executor.execute_test_suite(test_suite)
    assert result.branch_coverage == 75.0
