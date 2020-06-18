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
"""Provides an executor that executes generated sequences."""
import contextlib
import importlib
import logging
import os
from typing import List

import astor

import pynguin.configuration as config
import pynguin.testcase.execution.executioncontext as ctx
import pynguin.testcase.execution.executionresult as res
import pynguin.testcase.testcase as tc
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

    def get_tracer(self) -> ExecutionTracer:
        """Provide access to the execution tracer.

        Returns:
            The execution tracer
        """
        return self._tracer

    def execute(self, test_cases: List[tc.TestCase]) -> res.ExecutionResult:
        """Executes all statements of all test cases in a test suite.

        Args:
            test_cases: The list of test cases that should be executed.

        Returns:
            Result of the execution
        """
        result = res.ExecutionResult()
        self._tracer.clear_trace()

        with open(os.devnull, mode="w") as null_file:
            with contextlib.redirect_stdout(null_file):
                for test_case in test_cases:
                    exec_ctx = ctx.ExecutionContext(test_case)
                    self._execute_nodes(exec_ctx, result)
                self._collect_execution_trace(result)
        return result

    def _execute_nodes(
        self, exec_ctx: ctx.ExecutionContext, result: res.ExecutionResult,
    ):
        for idx, node in enumerate(exec_ctx.executable_nodes()):
            try:
                if self._logger.isEnabledFor(logging.DEBUG):
                    self._logger.debug("Executing %s", astor.to_source(node))
                code = compile(node, "<ast>", "exec")
                # pylint: disable=exec-used
                exec(code, exec_ctx.global_namespace, exec_ctx.local_namespace)  # nosec
            except Exception as err:  # pylint: disable=broad-except
                failed_stmt = astor.to_source(node)
                TestCaseExecutor._logger.debug(
                    "Failed to execute statement:\n%s%s", failed_stmt, err.args
                )
                result.report_new_thrown_exception(idx, err)
                break

    def _collect_execution_trace(self, result: res.ExecutionResult) -> None:
        """Collect the fitness after each execution.

        Also clear the tracking results so far.

        Args:
            result: The execution result
        """
        result.execution_trace = self._tracer.get_trace()
        self._tracer.clear_trace()
