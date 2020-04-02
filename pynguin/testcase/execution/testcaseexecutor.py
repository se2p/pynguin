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
from typing import Optional

import astor
from coverage import Coverage, CoverageException, CoverageData

import pynguin.configuration as config
import pynguin.testcase.execution.executionresult as res
import pynguin.testcase.testcase as tc
import pynguin.testsuite.testsuitechromosome as tsc
from pynguin.instrumentation.basis import get_tracer
from pynguin.testcase.execution.abstractexecutor import AbstractExecutor
from pynguin.testcase.execution.executiontracer import ExecutionTracer


class TestCaseExecutor(AbstractExecutor):
    """An executor that executes the generated test cases."""

    _logger = logging.getLogger(__name__)

    def __init__(self):
        """Initializes the executor. Loads the module under test."""
        super().__init__()
        if config.INSTANCE.measure_coverage:
            self._coverage = Coverage(
                branch=False, config_file=False, source=[config.INSTANCE.module_name]
            )
        else:
            self._coverage = None
        self._import_coverage = self._get_import_coverage()

    def _get_import_coverage(self) -> Optional[CoverageData]:
        """Collect coverage data on the module under test when it is imported.

        Theoretically coverage.py could store the data in memory instead of writing it
        to a file. But in this case, the merging of different runs doesn't work.
        """
        if not config.INSTANCE.measure_coverage:
            return None
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

    def execute(self, test_case: tc.TestCase) -> res.ExecutionResult:
        """Executes the statements in a test case.

        The return value indicates, whether or not the execution was successful,
        i.e., whether or not any unexpected exceptions were thrown.

        :param test_case: The test case that shall be executed
        :return: Result of the execution
        """
        result = res.ExecutionResult()
        if config.INSTANCE.measure_coverage:
            self._coverage.erase()
            self._coverage.get_data().update(self._import_coverage)

        self.setup(test_case)
        with open(os.devnull, mode="w") as null_file:
            with contextlib.redirect_stdout(null_file):
                self._execute_ast_nodes(result)
                self._collect_coverage(result)
                self._collect_fitness(result)
        return result

    def execute_test_suite(
        self, test_suite: tsc.TestSuiteChromosome
    ) -> res.ExecutionResult:
        """Executes all statements of all test cases in a test suite.

        :param test_suite: The list of test cases, i.e., the test suite
        :return: Result of the execution
        """
        result = res.ExecutionResult()
        if config.INSTANCE.measure_coverage:
            self._coverage.erase()
            self._coverage.get_data().update(self._import_coverage)

        with open(os.devnull, mode="w") as null_file:
            with contextlib.redirect_stdout(null_file):
                for test_case in test_suite.test_chromosomes:
                    self.setup(test_case)
                    self._execute_ast_nodes(result)
                self._collect_coverage(result)
                self._collect_fitness(result)
        return result

    def _execute_ast_nodes(
        self, result: res.ExecutionResult,
    ):
        for idx, node in enumerate(self._ast_nodes):
            try:
                self._logger.debug("Executing %s", astor.to_source(node))
                code = compile(self.wrap_node_in_module(node), "<ast>", "exec")
                if config.INSTANCE.measure_coverage:
                    self._coverage.start()
                # pylint: disable=exec-used
                exec(code, self._global_namespace, self._local_namespace)
            except Exception as err:  # pylint: disable=broad-except
                failed_stmt = astor.to_source(node)
                TestCaseExecutor._logger.info(
                    "Failed to execute statement:\n%s%s", failed_stmt, err.args
                )
                result.report_new_thrown_exception(idx, err)
                break
            finally:
                if config.INSTANCE.measure_coverage:
                    self._coverage.stop()

    def _collect_coverage(self, result: res.ExecutionResult) -> float:
        try:
            if config.INSTANCE.measure_coverage:
                result.branch_coverage = self._coverage.report()
            else:
                result.branch_coverage = 0
            self._logger.debug(
                "Achieved coverage after execution: %s", result.branch_coverage
            )
            return result.branch_coverage
        except CoverageException:
            # No call on the tested module?
            return -1

    @staticmethod
    def _collect_fitness(result: res.ExecutionResult):
        """
        Collect the fitness after each execution.
        Also clear the tracking results so far.
        """
        if config.INSTANCE.algorithm.use_instrumentation:
            tracer = get_tracer(sys.modules[config.INSTANCE.module_name])
            result.execution_trace = tracer.get_trace()
            tracer.clear_trace()
