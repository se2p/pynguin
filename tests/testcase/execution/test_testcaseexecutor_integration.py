#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Integration tests for the executor."""

import ast
import importlib
import threading

from queue import Empty
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

import pynguin.configuration as config

from pynguin.analyses.constants import EmptyConstantProvider
from pynguin.analyses.module import generate_test_cluster
from pynguin.analyses.seeding import AstToTestCaseTransformer
from pynguin.instrumentation.machinery import install_import_hook
from pynguin.instrumentation.tracer import ExecutionTracer
from pynguin.testcase.execution import ModuleProvider
from pynguin.testcase.execution import TestCaseExecutor
from pynguin.testcase.statement import IntPrimitiveStatement
from pynguin.testcase.statement import MethodStatement


def test_simple_execution(default_test_case):
    config.configuration.module_name = "tests.fixtures.accessibles.accessible"
    tracer = ExecutionTracer()
    tracer.current_thread_identifier = threading.current_thread().ident
    with install_import_hook(config.configuration.module_name, tracer):
        module = importlib.import_module(config.configuration.module_name)
        importlib.reload(module)
        default_test_case.add_statement(IntPrimitiveStatement(default_test_case, 5))
        executor = TestCaseExecutor(tracer)
        assert not executor.execute(default_test_case).has_test_exceptions()


def test_illegal_call(method_mock, default_test_case):
    config.configuration.module_name = "tests.fixtures.accessibles.accessible"
    int_stmt = IntPrimitiveStatement(default_test_case, 5)
    method_stmt = MethodStatement(default_test_case, method_mock, int_stmt.ret_val)
    default_test_case.add_statement(int_stmt)
    default_test_case.add_statement(method_stmt)
    tracer = ExecutionTracer()
    tracer.current_thread_identifier = threading.current_thread().ident
    with install_import_hook(config.configuration.module_name, tracer):
        module = importlib.import_module(config.configuration.module_name)
        importlib.reload(module)
        executor = TestCaseExecutor(tracer)
        result = executor.execute(default_test_case)
        assert result.has_test_exceptions()


def test_no_exceptions(short_test_case):
    config.configuration.module_name = "tests.fixtures.accessibles.accessible"
    tracer = ExecutionTracer()
    tracer.current_thread_identifier = threading.current_thread().ident
    with install_import_hook(config.configuration.module_name, tracer):
        module = importlib.import_module(config.configuration.module_name)
        importlib.reload(module)
        executor = TestCaseExecutor(tracer)
        result = executor.execute(short_test_case)
        assert not result.has_test_exceptions()


def test_instrumentation(short_test_case):
    config.configuration.module_name = "tests.fixtures.accessibles.accessible"
    config.configuration.statistics_output.coverage_metrics = [config.CoverageMetric.CHECKED]
    tracer = ExecutionTracer()
    tracer.current_thread_identifier = threading.current_thread().ident
    with install_import_hook(config.configuration.module_name, tracer):
        module = importlib.import_module(config.configuration.module_name)
        importlib.reload(module)
        executor = TestCaseExecutor(tracer)
        result = executor.execute(short_test_case)
        assert not result.has_test_exceptions()
        assert result.execution_trace.executed_instructions


def test_observers(short_test_case):
    tracer = ExecutionTracer()
    tracer.current_thread_identifier = threading.current_thread().ident
    executor = TestCaseExecutor(tracer)
    observer = MagicMock()
    observer.remote_observer = MagicMock()
    observer.remote_observer.before_statement_execution.side_effect = lambda _x, y, _z: y
    executor.add_observer(observer)
    executor.execute(short_test_case)
    assert observer.remote_observer.before_test_case_execution.call_count == 1
    assert observer.remote_observer.before_statement_execution.call_count == 2
    assert observer.remote_observer.after_statement_execution.call_count == 2
    assert observer.remote_observer.after_test_case_execution.call_count == 1
    assert observer.before_remote_test_case_execution.call_count == 1
    assert observer.after_remote_test_case_execution.call_count == 1


def test_observers_clear():
    tracer = ExecutionTracer()
    tracer.current_thread_identifier = threading.current_thread().ident
    executor = TestCaseExecutor(tracer)
    observer = MagicMock()
    executor.add_observer(observer)
    assert executor._observers == [observer]
    executor.clear_observers()
    assert executor._observers == []


def test_module_provider():
    tracer = ExecutionTracer()
    tracer.current_thread_identifier = threading.current_thread().ident
    prov = ModuleProvider()
    executor = TestCaseExecutor(tracer, prov)
    assert executor.module_provider == prov


@pytest.mark.filterwarnings("ignore::pytest.PytestUnhandledThreadExceptionWarning")
def test_killing_endless_loop():
    config.configuration.module_name = "tests.fixtures.examples.loop"
    module_name = config.configuration.module_name
    tracer = ExecutionTracer()
    tracer.current_thread_identifier = threading.current_thread().ident
    with install_import_hook(module_name, tracer):
        # Need to force reload in order to apply instrumentation
        module = importlib.import_module(module_name)
        importlib.reload(module)

        executor = TestCaseExecutor(tracer)
        cluster = generate_test_cluster(module_name)
        transformer = AstToTestCaseTransformer(
            cluster,
            False,  # noqa: FBT003
            EmptyConstantProvider(),
        )
        transformer.visit(
            ast.parse(
                """def test_case_0():
    anything = module_0.loop_with_condition()
"""
            )
        )
        test_case = transformer.testcases[0]
        executor.execute(test_case)
        # Running this with a debugger may break these assertions
        for thread in threading.enumerate():
            if "_execute_test_case" in thread.name:
                thread.join()
        assert len(threading.enumerate()) == 1  # Only main thread should be alive.


@pytest.mark.filterwarnings("ignore::pytest.PytestUnhandledThreadExceptionWarning")
def test_empty_queue_with_llm_api_key(default_test_case):
    """Test handling of Empty exception when LLM API key is configured."""
    # Set up LLM API key configuration
    original_api_key = config.configuration.large_language_model.api_key
    config.configuration.large_language_model.api_key = "test_api_key"

    try:
        config.configuration.module_name = "tests.fixtures.accessibles.accessible"
        tracer = ExecutionTracer()
        tracer.current_thread_identifier = threading.current_thread().ident

        with install_import_hook(config.configuration.module_name, tracer):
            module = importlib.import_module(config.configuration.module_name)
            importlib.reload(module)

            default_test_case.add_statement(IntPrimitiveStatement(default_test_case, 5))
            executor = TestCaseExecutor(tracer)

            # Mock Queue.get to raise Empty exception
            with patch("queue.Queue.get", side_effect=Empty()):
                # This should not raise an exception but return a result with timeout=True
                result = executor.execute(default_test_case)
                assert result.timeout is True
    finally:
        # Restore original configuration
        config.configuration.large_language_model.api_key = original_api_key


@pytest.mark.filterwarnings("ignore::pytest.PytestUnhandledThreadExceptionWarning")
def test_empty_queue_without_llm_api_key(default_test_case):
    """Test handling of Empty exception when LLM API key is not configured."""
    # Ensure LLM API key is not configured
    original_api_key = config.configuration.large_language_model.api_key
    config.configuration.large_language_model.api_key = None

    try:
        config.configuration.module_name = "tests.fixtures.accessibles.accessible"
        tracer = ExecutionTracer()
        tracer.current_thread_identifier = threading.current_thread().ident

        with install_import_hook(config.configuration.module_name, tracer):
            module = importlib.import_module(config.configuration.module_name)
            importlib.reload(module)

            default_test_case.add_statement(IntPrimitiveStatement(default_test_case, 5))
            executor = TestCaseExecutor(tracer)

            # Mock Queue.get to raise Empty exception
            with patch("queue.Queue.get", side_effect=Empty()):
                # This should not raise an exception but return a result with timeout=True
                result = executor.execute(default_test_case)
                assert result.timeout is True
    finally:
        # Restore original configuration
        config.configuration.large_language_model.api_key = original_api_key
