#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Integration tests for the executor."""
import importlib
from unittest.mock import MagicMock

import pynguin.configuration as config
import pynguin.testcase.defaulttestcase as dtc
import pynguin.testcase.statements.parametrizedstatements as param_stmt
import pynguin.testcase.statements.primitivestatements as prim_stmt
from pynguin.instrumentation.machinery import install_import_hook
from pynguin.testcase.execution.executiontracer import ExecutionTracer
from pynguin.testcase.execution.testcaseexecutor import TestCaseExecutor


def test_simple_execution():
    config.configuration.module_name = "tests.fixtures.accessibles.accessible"
    tracer = ExecutionTracer()
    with install_import_hook(config.configuration.module_name, tracer):
        module = importlib.import_module(config.configuration.module_name)
        importlib.reload(module)
        test_case = dtc.DefaultTestCase()
        test_case.add_statement(prim_stmt.IntPrimitiveStatement(test_case, 5))
        executor = TestCaseExecutor(tracer)
        assert not executor.execute(test_case).has_test_exceptions()


def test_illegal_call(method_mock):
    config.configuration.module_name = "tests.fixtures.accessibles.accessible"
    test_case = dtc.DefaultTestCase()
    int_stmt = prim_stmt.IntPrimitiveStatement(test_case, 5)
    method_stmt = param_stmt.MethodStatement(test_case, method_mock, int_stmt.ret_val)
    test_case.add_statement(int_stmt)
    test_case.add_statement(method_stmt)
    tracer = ExecutionTracer()
    with install_import_hook(config.configuration.module_name, tracer):
        module = importlib.import_module(config.configuration.module_name)
        importlib.reload(module)
        executor = TestCaseExecutor(tracer)
        result = executor.execute(test_case)
        assert result.has_test_exceptions()


def test_no_exceptions(short_test_case):
    config.configuration.module_name = "tests.fixtures.accessibles.accessible"
    tracer = ExecutionTracer()
    with install_import_hook(config.configuration.module_name, tracer):
        module = importlib.import_module(config.configuration.module_name)
        importlib.reload(module)
        executor = TestCaseExecutor(tracer)
        result = executor.execute(short_test_case)
        assert not result.has_test_exceptions()


def test_observers(short_test_case):
    tracer = ExecutionTracer()
    executor = TestCaseExecutor(tracer)
    observer = MagicMock()
    executor.add_observer(observer)
    executor.execute(short_test_case)
    assert observer.before_test_case_execution.call_count == 1
    assert observer.before_statement_execution.call_count == 2
    assert observer.after_statement_execution.call_count == 2
    assert observer.after_test_case_execution.call_count == 1
