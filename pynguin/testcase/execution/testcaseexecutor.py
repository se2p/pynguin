#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides an executor that executes generated sequences."""
import contextlib
import importlib
import logging
import os
from typing import List, Optional

import astor

import pynguin.configuration as config
import pynguin.testcase.execution.executioncontext as ctx
import pynguin.testcase.execution.executionresult as res
import pynguin.testcase.statements.statement as stmt
import pynguin.testcase.testcase as tc
from pynguin.analyses.duckmock.typeanalysis import TypeAnalysis
from pynguin.testcase.execution.executionobserver import ExecutionObserver
from pynguin.testcase.execution.executiontracer import ExecutionTracer


class TestCaseExecutor:
    """An executor that executes the generated test cases."""

    _logger = logging.getLogger(__name__)

    def __init__(self, tracer: ExecutionTracer) -> None:
        """Load the module under test.

        Args:
            tracer: the execution tracer
        """
        importlib.import_module(config.INSTANCE.module_name)
        self._tracer = tracer
        self._observers: List[ExecutionObserver] = []
        self._type_analysis: Optional[TypeAnalysis] = None

    def add_observer(self, observer: ExecutionObserver) -> None:
        """Add an execution observer.

        Args:
            observer: the observer to be added.
        """
        self._observers.append(observer)

    def get_tracer(self) -> ExecutionTracer:
        """Provide access to the execution tracer.

        Returns:
            The execution tracer
        """
        return self._tracer

    @property
    def type_analysis(self) -> Optional[TypeAnalysis]:
        """Provide access to the optional type analysis.

        Returns:
            The optional type analysis
        """
        return self._type_analysis

    @type_analysis.setter
    def type_analysis(self, type_analysis: TypeAnalysis) -> None:
        """Sets the type analysis.

        Args:
            type_analysis: A type-instance, must not be `None`
        """
        assert type_analysis is not None
        self._type_analysis = type_analysis

    def execute(self, test_case: tc.TestCase) -> res.ExecutionResult:
        """Executes all statements of all test cases in a test suite.

        Args:
            test_case: the test case that should be executed.

        Returns:
            Result of the execution
        """
        result = res.ExecutionResult()
        self._tracer.clear_trace()

        with open(os.devnull, mode="w") as null_file:
            with contextlib.redirect_stdout(null_file):
                exec_ctx = ctx.ExecutionContext(test_case)
                self._execute_nodes(exec_ctx, test_case, result)
                self._collect_execution_trace(result)
        return result

    def _execute_nodes(
        self,
        exec_ctx: ctx.ExecutionContext,
        test_case: tc.TestCase,
        result: res.ExecutionResult,
    ):
        for idx, node in enumerate(exec_ctx.executable_nodes()):
            if self._logger.isEnabledFor(logging.DEBUG):
                self._logger.debug("Executing %s", astor.to_source(node))
            code = compile(node, "<ast>", "exec")
            try:
                # pylint: disable=exec-used
                exec(code, exec_ctx.global_namespace, exec_ctx.local_namespace)  # nosec
            except Exception as err:  # pylint: disable=broad-except
                failed_stmt = astor.to_source(node)
                TestCaseExecutor._logger.debug(
                    "Failed to execute statement:\n%s%s", failed_stmt, err.args
                )
                result.report_new_thrown_exception(idx, err)
                break
            self._observe_after(test_case.get_statement(idx), exec_ctx)

    def _collect_execution_trace(self, result: res.ExecutionResult) -> None:
        """Collect the execution trace after each executed test case.
        Also clear the tracking results so far.

        Args:
            result: The execution result
        """
        result.execution_trace = self._tracer.get_trace()
        self._tracer.clear_trace()

    def _observe_after(self, statement: stmt.Statement, exec_ctx: ctx.ExecutionContext):
        self._tracer.disable()
        try:
            for observer in self._observers:
                observer.after_statement_execution(statement, exec_ctx)
        finally:
            self._tracer.enable()
