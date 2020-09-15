#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""A test-case executor utilising duck mocks."""
import contextlib
import logging
import os
from typing import List, Optional

import astor

import pynguin.testcase.execution.duckexecutioncontext as ctx
import pynguin.testcase.execution.executionresult as res
import pynguin.testcase.testcase as tc
from pynguin.analyses.duckmock.typeanalysis import TypeAnalysis
from pynguin.testcase.execution.executiontracer import ExecutionTracer
from pynguin.testcase.execution.testcaseexecutor import TestCaseExecutor


class DuckTestCaseExecutor(TestCaseExecutor):
    """A test-case executor utilising duck mocks."""

    def __init__(self, tracer: ExecutionTracer) -> None:
        super().__init__(tracer)
        self._type_analysis: Optional[TypeAnalysis] = None

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
            type_analysis: A type-analysis instance, must not be `None`
        """
        assert type_analysis is not None
        self._type_analysis = type_analysis

    def execute(self, test_cases: List[tc.TestCase]) -> res.ExecutionResult:
        result = res.ExecutionResult()
        self._tracer.clear_trace()

        with open(os.devnull, mode="w") as null_file:
            with contextlib.redirect_stdout(null_file):
                for test_case in test_cases:
                    exec_ctx = ctx.DuckExecutionContext(test_case)
                    self._execute_nodes(exec_ctx, result)
                self._collect_execution_trace(result)
        return result

    def _execute_nodes(
        self,
        exec_ctx: ctx.ExecutionContext,
        result: res.ExecutionResult,
    ):
        for idx, node in enumerate(exec_ctx.executable_nodes()):
            try:
                if self._logger.isEnabledFor(logging.DEBUG):
                    self._logger.debug("Executing %s", astor.to_source(node))
                code = compile(node, "<ast>", "exec")
                # pylint: disable=exec-used
                exec(code, exec_ctx.global_namespace, exec_ctx.local_namespace)  # nosec
                # TODO(sl) extract information from duck now
                self._extract_duck_information()
            except Exception as err:  # pylint: disable=broad-except
                failed_stmt = astor.to_source(node)
                self._logger.debug(
                    "Failed to execute statement:\n%s%s", failed_stmt, err.args
                )
                result.report_new_thrown_exception(idx, err)
                break

    def _extract_duck_information(self):
        pass
