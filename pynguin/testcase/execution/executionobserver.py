#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provide an execution observer"""
from abc import abstractmethod
from typing import Optional

import pynguin.testcase.execution.executionresult as res
import pynguin.testcase.statements.statement as stmt
import pynguin.testcase.testcase as tc
from pynguin.testcase.execution.executioncontext import ExecutionContext


class ExecutionObserver:
    """An Observer that can be used to observe statement execution"""

    @abstractmethod
    def before_test_case_execution(self, test_case: tc.TestCase):
        """Called before test case execution."""

    @abstractmethod
    def after_test_case_execution(
        self, test_case: tc.TestCase, result: res.ExecutionResult
    ):
        """Called after test case execution."""

    @abstractmethod
    def before_statement_execution(
        self, statement: stmt.Statement, exec_ctx: ExecutionContext
    ):
        """Called before a statement is executed.

        Args:
            statement: the statement about to be executed.
            exec_ctx: the current execution context.
        """

    @abstractmethod
    def after_statement_execution(
        self,
        statement: stmt.Statement,
        exec_ctx: ExecutionContext,
        exception: Optional[Exception] = None,
    ) -> None:
        """
        Called after a statement was executed.

        Args:
            statement: the statement that was executed.
            exec_ctx: the current execution context.
            exception: the exception that was thrown, if any.
        """
