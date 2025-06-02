#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019-2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Tests for the exception handling in SubprocessTestCaseExecutor."""

import logging
import multiprocessing.connection as mp_conn
import unittest.mock

from pynguin.instrumentation.tracer import ExecutionTracer
from pynguin.testcase.execution import ModuleProvider
from pynguin.testcase.execution import SubprocessTestCaseExecutor


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
