#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides an executor that executes generated sequences."""
import contextlib
import logging
import multiprocessing
import os
import threading
from typing import List, Optional

import astor

import pynguin.testcase.execution.executioncontext as ctx
import pynguin.testcase.execution.executionobserver as eo
import pynguin.testcase.execution.executionresult as res
import pynguin.testcase.statements.statement as stmt
import pynguin.testcase.testcase as tc
from pynguin.testcase.execution.executiontracer import ExecutionTracer


class TestCaseExecutor:
    """An executor that executes the generated test cases."""

    _logger = logging.getLogger(__name__)

    def __init__(self, tracer: ExecutionTracer) -> None:
        """Create new test case executor.

        Args:
            tracer: the execution tracer
        """
        self._tracer = tracer
        self._observers: List[eo.ExecutionObserver] = []

    def add_observer(self, observer: eo.ExecutionObserver) -> None:
        """Add an execution observer.

        Args:
            observer: the observer to be added.
        """
        self._observers.append(observer)

    @property
    def tracer(self) -> ExecutionTracer:
        """Provide access to the execution tracer.

        Returns:
            The execution tracer
        """
        return self._tracer

    def execute(self, test_case: tc.TestCase) -> res.ExecutionResult:
        """Executes all statements of the given test case.

        Args:
            test_case: the test case that should be executed.

        Returns:
            Result of the execution
        """
        with open(os.devnull, mode="w") as null_file:
            with contextlib.redirect_stdout(null_file):
                self._before_test_case_execution(test_case)
                return_queue: multiprocessing.Queue = multiprocessing.Queue()
                thread = threading.Thread(
                    target=self._execute_test_case, args=(test_case, return_queue)
                )
                thread.start()
                thread.join(timeout=5 * len(test_case.statements))
                if not thread.is_alive():
                    result = return_queue.get()
                else:
                    result = res.ExecutionResult()
                    result.report_new_thrown_exception(0, TimeoutError())
                self._after_test_case_execution(test_case, result)
        return result

    def _before_test_case_execution(self, test_case: tc.TestCase) -> None:
        self._tracer.clear_trace()
        for observer in self._observers:
            observer.before_test_case_execution(test_case)

    def _execute_test_case(
        self,
        test_case: tc.TestCase,
        result_queue: multiprocessing.Queue,
    ) -> None:
        result = res.ExecutionResult()
        exec_ctx = ctx.ExecutionContext()
        for idx, statement in enumerate(test_case.statements):
            self._before_statement_execution(statement, exec_ctx)
            exception = self._execute_statement(statement, exec_ctx)
            self._after_statement_execution(statement, exec_ctx, exception)
            if exception is not None:
                result.report_new_thrown_exception(idx, exception)
                break
        result_queue.put(result)

    def _after_test_case_execution(
        self, test_case: tc.TestCase, result: res.ExecutionResult
    ) -> None:
        """Collect the execution trace after each executed test case."""
        result.execution_trace = self._tracer.get_trace()
        for observer in self._observers:
            observer.after_test_case_execution(test_case, result)

    def _before_statement_execution(
        self, statement: stmt.Statement, exec_ctx: ctx.ExecutionContext
    ) -> None:
        # We need to disable the tracer, because an observer might interact with an
        # object of the SUT via the ExecutionContext and trigger code execution, which
        # is not caused by the test case and should therefore not be in the trace.
        self._tracer.disable()
        try:
            for observer in self._observers:
                observer.before_statement_execution(statement, exec_ctx)
        finally:
            self._tracer.enable()

    def _execute_statement(
        self, statement: stmt.Statement, exec_ctx: ctx.ExecutionContext
    ) -> Optional[Exception]:
        ast_node = exec_ctx.executable_node_for(statement)
        if self._logger.isEnabledFor(logging.DEBUG):
            self._logger.debug("Executing %s", astor.to_source(ast_node))
        code = compile(ast_node, "<ast>", "exec")
        try:
            # pylint: disable=exec-used
            exec(code, exec_ctx.global_namespace, exec_ctx.local_namespace)  # nosec
        except Exception as err:  # pylint: disable=broad-except
            failed_stmt = astor.to_source(ast_node)
            TestCaseExecutor._logger.debug(
                "Failed to execute statement:\n%s%s", failed_stmt, err.args
            )
            return err
        return None

    def _after_statement_execution(
        self,
        statement: stmt.Statement,
        exec_ctx: ctx.ExecutionContext,
        exception: Optional[Exception],
    ):
        # See _before_statement_execution
        self._tracer.disable()
        try:
            for observer in self._observers:
                observer.after_statement_execution(statement, exec_ctx, exception)
        finally:
            self._tracer.enable()
