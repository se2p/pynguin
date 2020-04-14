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
import sys
from typing import Optional, List

import astor
from coverage import Coverage, CoverageException, CoverageData

import pynguin.configuration as config
import pynguin.testcase.execution.executionresult as res
import pynguin.testcase.testcase as tc
import pynguin.testcase.execution.executioncontext as ctx
from pynguin.instrumentation.basis import get_tracer
from pynguin.testcase.execution.executiontracer import ExecutionTracer


class TestCaseExecutor:
    """An executor that executes the generated test cases."""

    _logger = logging.getLogger(__name__)

    def __init__(self):
        """Initializes the executor. Loads the module under test."""
        self._coverage = Coverage(
            branch=False, config_file=False, source=[config.INSTANCE.module_name]
        )
        self._import_coverage = self._get_import_coverage()

    def _get_import_coverage(self) -> Optional[CoverageData]:
        """Collect coverage data on the module under test when it is imported.

        Theoretically coverage.py could store the data in memory instead of writing it
        to a file. But in this case, the merging of different runs doesn't work.
        """
        cov_data = CoverageData(basename="coverage.pynguin.import")
        cov_data.erase()
        try:
            self._coverage.start()
            imported = importlib.import_module(config.INSTANCE.module_name)
            importlib.reload(imported)
        finally:
            self._coverage.stop()
            cov_data.update(self._coverage.get_data())
            cov_data.write()
        self._coverage.erase()
        return cov_data

    @staticmethod
    def get_tracer() -> ExecutionTracer:
        """Provide access to the execution tracer."""
        return get_tracer(sys.modules[config.INSTANCE.module_name])

    def execute(
        self, test_cases: List[tc.TestCase], measure_coverage: bool = False
    ) -> res.ExecutionResult:
        """Executes all statements of all test cases in a test suite.

        :param test_cases: The list of test cases that should be executed.
        :param measure_coverage: Measure coverage during execution.
        :return: Result of the execution
        """
        result = res.ExecutionResult()
        if config.INSTANCE.algorithm.use_instrumentation:
            self.get_tracer().clear_trace()
        if measure_coverage:
            self._coverage.erase()
            self._coverage.get_data().update(self._import_coverage)

        with open(os.devnull, mode="w") as null_file:
            with contextlib.redirect_stdout(null_file):
                for test_case in test_cases:
                    exec_ctx = ctx.ExecutionContext(test_case)
                    self._execute_nodes(exec_ctx, result, measure_coverage)
                self._collect_coverage(result, measure_coverage)
                self._collect_execution_trace(result)
        return result

    def _execute_nodes(
        self,
        exec_ctx: ctx.ExecutionContext,
        result: res.ExecutionResult,
        measure_coverage: bool,
    ):
        for idx, node in enumerate(exec_ctx.executable_nodes()):
            try:
                if self._logger.isEnabledFor(logging.DEBUG):
                    self._logger.debug("Executing %s", astor.to_source(node))
                code = compile(node, "<ast>", "exec")
                if measure_coverage:
                    self._coverage.start()
                # pylint: disable=exec-used
                exec(code, exec_ctx.global_namespace, exec_ctx.local_namespace)
            except Exception as err:  # pylint: disable=broad-except
                failed_stmt = astor.to_source(node)
                TestCaseExecutor._logger.info(
                    "Failed to execute statement:\n%s%s", failed_stmt, err.args
                )
                result.report_new_thrown_exception(idx, err)
                break
            finally:
                if measure_coverage:
                    self._coverage.stop()

    def _collect_coverage(self, result: res.ExecutionResult, measure_coverage: bool):
        if measure_coverage:
            try:
                result.branch_coverage = self._coverage.report()
            except CoverageException:
                # No call on the tested module?
                self._logger.debug("No call on the SUT. Setting coverage to 0")
                result.branch_coverage = 0.0
            self._logger.debug(
                "Achieved coverage after execution: %s", result.branch_coverage
            )

    @staticmethod
    def _collect_execution_trace(result: res.ExecutionResult):
        """
        Collect the fitness after each execution.
        Also clear the tracking results so far.
        """
        if config.INSTANCE.algorithm.use_instrumentation:
            tracer = TestCaseExecutor.get_tracer()
            result.execution_trace = tracer.get_trace()
            tracer.clear_trace()
