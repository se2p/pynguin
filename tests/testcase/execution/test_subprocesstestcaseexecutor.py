#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019-2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Tests for the exception handling in SubprocessTestCaseExecutor."""

import importlib
import inspect
import logging
import multiprocessing.connection as mp_conn
import os
import signal
import threading
import unittest.mock

from typing import Any
from unittest.mock import patch

import pytest

import pynguin.configuration as config
import pynguin.testcase.defaulttestcase as dtc
import pynguin.testcase.statement as stmt

from pynguin.analyses.module import ModuleTestCluster
from pynguin.analyses.typesystem import InferredSignature
from pynguin.analyses.typesystem import NoneType
from pynguin.instrumentation.machinery import install_import_hook
from pynguin.instrumentation.tracer import ExecutionTracer
from pynguin.testcase.execution import ModuleProvider
from pynguin.testcase.execution import SubprocessTestCaseExecutor
from pynguin.utils.generic.genericaccessibleobject import GenericFunction
from tests.fixtures.crash.seg_fault import cause_segmentation_fault


class SegFaultOutputSuppressionContext:
    """Context manager to suppress SIGSEGV (segmentation fault) by exiting silently.

    Signal only works in main thread of the main interpreter, due to which this suppression
    context must not be used within subprocess execution.
    """

    def __init__(self) -> None:
        """Create a new context manager that suppresses SIGSEGV."""
        self._original_sigsegv_handler = signal.getsignal(signal.SIGSEGV)
        self._devnull: Any | None = None

    def _handle_sigsegv(self, sig, frame):
        os._exit(signal.SIGSEGV)

    def __enter__(self):
        signal.signal(signal.SIGSEGV, self._handle_sigsegv)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        signal.signal(signal.SIGSEGV, self._original_sigsegv_handler)
        if self._devnull is not None:
            self._devnull.close()


@pytest.fixture
def cause_seg_fault_mock(type_system) -> GenericFunction:
    return GenericFunction(
        function=cause_segmentation_fault,
        inferred_signature=InferredSignature(
            signature=inspect.Signature(),
            original_return_type=NoneType(),
            original_parameters={},
            type_system=type_system,
        ),
    )


def test_subprocess_exception_suppression():
    """Test that exceptions in the subprocess are suppressed."""
    # Create a mock for the _replace_tracer method to raise an exception
    with unittest.mock.patch.object(
        SubprocessTestCaseExecutor, "_replace_tracer"
    ) as mock_replace_tracer:
        # Set up the mock to raise an exception
        mock_replace_tracer.side_effect = Exception("Test exception")

        # Create the necessary arguments for _execute_test_cases_in_subprocess
        tracer = ExecutionTracer()
        module_provider = unittest.mock.MagicMock(spec=ModuleProvider)
        maximum_test_execution_timeout = 5
        test_execution_time_per_statement = 1
        remote_observers = ()
        test_cases = ()
        references_bindings = ()
        sending_connection = unittest.mock.MagicMock(spec=mp_conn.Connection)

        # Call the method directly
        # This should not raise an exception because the exception should be caught
        # and suppressed inside the method
        SubprocessTestCaseExecutor._execute_test_cases_in_subprocess(
            tracer,
            module_provider,
            maximum_test_execution_timeout,
            test_execution_time_per_statement,
            remote_observers,
            test_cases,
            references_bindings,
            sending_connection,
        )

        # Verify that the mock was called
        mock_replace_tracer.assert_called_once_with(tracer)

        # Verify that sending_connection.send was not called
        # because an exception was raised before that point
        sending_connection.send.assert_not_called()


@pytest.fixture
def cause_seg_fault_test_case(cause_seg_fault_mock):
    test_case = dtc.DefaultTestCase(ModuleTestCluster(0))
    test_case.add_statement(stmt.FunctionStatement(test_case, cause_seg_fault_mock))
    return test_case


def test_subprocess_exception_logging(caplog):
    """Test that exceptions in the subprocess are logged."""
    # Set up logging capture
    caplog.set_level(logging.WARNING)

    # Create a mock for the _replace_tracer method to raise an exception
    with unittest.mock.patch.object(
        SubprocessTestCaseExecutor, "_replace_tracer"
    ) as mock_replace_tracer:
        # Set up the mock to raise an exception with a specific message
        exception_message = "Test exception for logging"
        mock_replace_tracer.side_effect = Exception(exception_message)

        # Create the necessary arguments for _execute_test_cases_in_subprocess
        tracer = ExecutionTracer()
        module_provider = unittest.mock.MagicMock(spec=ModuleProvider)
        maximum_test_execution_timeout = 5
        test_execution_time_per_statement = 1
        remote_observers = ()
        test_cases = ()
        references_bindings = ()
        sending_connection = unittest.mock.MagicMock(spec=mp_conn.Connection)

        # Call the method directly
        SubprocessTestCaseExecutor._execute_test_cases_in_subprocess(
            tracer,
            module_provider,
            maximum_test_execution_timeout,
            test_execution_time_per_statement,
            remote_observers,
            test_cases,
            references_bindings,
            sending_connection,
        )

        # Verify that the exception was logged
        assert f"Suppressed exception in subprocess: {exception_message}" in caplog.text


def test_crashing_execution(tmp_path, cause_seg_fault_test_case):
    # prevent test output into the tests directory
    config.configuration.test_case_output.crash_path = tmp_path
    config.configuration.module_name = "tests.fixtures.crash.seg_fault"

    subprocess_tracer = ExecutionTracer()
    subprocess_tracer.current_thread_identifier = threading.current_thread().ident

    with install_import_hook(config.configuration.module_name, subprocess_tracer):
        module = importlib.import_module(config.configuration.module_name)
        importlib.reload(module)
        subprocess_executor = SubprocessTestCaseExecutor(subprocess_tracer)
        with SegFaultOutputSuppressionContext():
            exit_code = subprocess_executor.execute_with_exit_code(cause_seg_fault_test_case)

    assert exit_code != 0, "Expected a non-zero exit code due to segmentation fault"


def test_eof_error_during_receiving_results(default_test_case):
    """Test handling of EOFError during receiving results from subprocess."""
    config.configuration.module_name = "tests.fixtures.accessibles.accessible"

    subprocess_tracer = ExecutionTracer()
    subprocess_tracer.current_thread_identifier = threading.current_thread().ident

    with install_import_hook(config.configuration.module_name, subprocess_tracer):
        module = importlib.import_module(config.configuration.module_name)
        importlib.reload(module)

        # Add a statement to the test case
        default_test_case.add_statement(stmt.IntPrimitiveStatement(default_test_case, 5))

        subprocess_executor = SubprocessTestCaseExecutor(subprocess_tracer)

        # Mock the connection and process
        with (
            patch("multiprocess.connection.Connection.poll", return_value=True),
            patch("multiprocess.connection.Connection.recv", side_effect=EOFError()),
            patch("multiprocess.Process.join"),
            patch("multiprocess.Process.exitcode", None),
            patch("multiprocess.Process.kill"),
        ):
            exit_code = subprocess_executor.execute_with_exit_code(default_test_case)
            assert exit_code is None


def test_empty_test_case_no_results(default_test_case):
    """Test handling of empty test case with no results."""
    config.configuration.module_name = "tests.fixtures.accessibles.accessible"

    subprocess_tracer = ExecutionTracer()
    subprocess_tracer.current_thread_identifier = threading.current_thread().ident

    with install_import_hook(config.configuration.module_name, subprocess_tracer):
        module = importlib.import_module(config.configuration.module_name)
        importlib.reload(module)

        # Ensure the test case is empty
        assert default_test_case.size() == 0

        subprocess_executor = SubprocessTestCaseExecutor(subprocess_tracer)

        # Mock the connection to return no results
        with patch("multiprocess.connection.Connection.poll", return_value=False):
            exit_code = subprocess_executor.execute_with_exit_code(default_test_case)

            # Should return 0 for empty test case
            assert exit_code == 0


def test_non_empty_test_case_no_results(short_test_case):
    """Test handling of non-empty test case with no results."""
    config.configuration.module_name = "tests.fixtures.accessibles.accessible"

    subprocess_tracer = ExecutionTracer()
    subprocess_tracer.current_thread_identifier = threading.current_thread().ident

    with install_import_hook(config.configuration.module_name, subprocess_tracer):
        module = importlib.import_module(config.configuration.module_name)
        importlib.reload(module)

        # Ensure the test case is not empty
        assert short_test_case.size() > 0

        subprocess_executor = SubprocessTestCaseExecutor(subprocess_tracer)

        # Mock the connection and process
        with (
            patch("multiprocess.connection.Connection.poll", return_value=False),
            patch("multiprocess.Process.exitcode", None),
            patch("multiprocess.Process.kill"),
        ):
            exit_code = subprocess_executor.execute_with_exit_code(short_test_case)
            assert exit_code is None
