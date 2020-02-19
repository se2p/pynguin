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
import ast
import contextlib
import importlib
import logging
import os
import sys
from typing import Tuple, Union, Any, List, Dict, Optional

import astor
from coverage import Coverage, CoverageException, CoverageData

import pynguin.testcase.testcase as tc
import pynguin.testcase.statement_to_ast as stmt_to_ast
import pynguin.testcase.execution.executionresult as res
import pynguin.configuration as config
from pynguin.instrumentation.basis import get_tracer
from pynguin.utils.proxy import MagicProxy


def _recording_isinstance(
    obj: Any, obj_type: Union[type, Tuple[Union[type, tuple], ...]]
) -> bool:
    if isinstance(obj, MagicProxy):
        # pylint: disable=protected-access
        obj._instance_check_type = obj_type  # type: ignore
    return isinstance(obj, obj_type)


# pylint: disable=too-few-public-methods
class TestCaseExecutor:
    """An executor that executes the generated test cases."""

    _logger = logging.getLogger(__name__)

    def __init__(self):
        """Initializes the executor. Loads the module under test."""
        if config.INSTANCE.measure_coverage:
            self._coverage = Coverage(
                branch=True, config_file=False, source=[config.INSTANCE.module_name]
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

        # TODO(fk) wrap new values in magic proxy.
        local_namespace: Dict[str, Any] = {}

        variable_names = stmt_to_ast.NamingScope()
        modules_aliases = stmt_to_ast.NamingScope(prefix="module")
        ast_nodes: List[ast.stmt] = TestCaseExecutor._to_ast_nodes(
            test_case, variable_names, modules_aliases
        )
        global_namespace: Dict[str, Any] = TestCaseExecutor._prepare_global_namespace(
            modules_aliases
        )
        with open(os.devnull, mode="w") as null_file:
            with contextlib.redirect_stdout(null_file):
                self._execute_ast_nodes(
                    ast_nodes, global_namespace, local_namespace, result
                )
                self._collect_coverage(result)
                self._collect_fitness(result)
        return result

    def execute_test_suite(self, test_cases: List[tc.TestCase]) -> res.ExecutionResult:
        """Executes all statements of all test cases in a test suite.

        :param test_cases: The list of test cases, i.e., the test suite
        :return: Result of the execution
        """
        TestCaseExecutor._logger.info(
            "Rerun execution of generated test suite to measure coverage (if "
            "requested by configuration)"
        )
        result = res.ExecutionResult()
        if config.INSTANCE.measure_coverage:
            self._coverage.erase()
            self._coverage.get_data().update(self._import_coverage)

        with open(os.devnull, mode="w") as null_file:
            with contextlib.redirect_stdout(null_file):
                for test_case in test_cases:
                    local_namespace: Dict[str, Any] = {}
                    variable_names = stmt_to_ast.NamingScope()
                    modules_aliases = stmt_to_ast.NamingScope(prefix="module")
                    ast_nodes: List[ast.stmt] = TestCaseExecutor._to_ast_nodes(
                        test_case, variable_names, modules_aliases
                    )
                    global_namespace: Dict[
                        str, Any
                    ] = TestCaseExecutor._prepare_global_namespace(modules_aliases)
                    self._execute_ast_nodes(
                        ast_nodes, global_namespace, local_namespace, result
                    )
                self._collect_coverage(result)
                self._collect_fitness(result)
        TestCaseExecutor._logger.info("Finished re-execution of generated test suite")
        return result

    def _execute_ast_nodes(
        self,
        ast_nodes: List[ast.stmt],
        global_namespace: Dict[str, Any],
        local_namespace: Dict[str, Any],
        result: res.ExecutionResult,
    ):
        for idx, node in enumerate(ast_nodes):
            try:
                self._logger.debug("Executing %s", astor.to_source(node))
                code = compile(self._wrap_node_in_module(node), "<ast>", "exec")
                if config.INSTANCE.measure_coverage:
                    self._coverage.start()
                # pylint: disable=exec-used
                exec(code, global_namespace, local_namespace)
            except Exception as err:  # pylint: disable=broad-except
                failed_stmt = astor.to_source(node)
                TestCaseExecutor._logger.warning(
                    "Failed to execute statement:\n%s%s", failed_stmt, err.args
                )
                result.report_new_thrown_exception(idx, err)
                break
            finally:
                if config.INSTANCE.measure_coverage:
                    self._coverage.stop()

    def _collect_coverage(self, result: res.ExecutionResult):
        try:
            if config.INSTANCE.measure_coverage:
                result.branch_coverage = self._coverage.report()
            else:
                result.branch_coverage = -1
            self._logger.debug(
                "Achieved coverage after execution: %s", result.branch_coverage
            )
        except CoverageException:
            # No call on the tested module?
            pass

    @staticmethod
    def _collect_fitness(result: res.ExecutionResult):
        """
        Collect the fitness after each execution.
        Also clear the tracking results so far.
        """
        if config.INSTANCE.algorithm.use_instrumentation:
            tracer = get_tracer(sys.modules[config.INSTANCE.module_name])
            result.fitness = tracer.get_fitness()
            tracer.clear_tracking()

    @staticmethod
    def _to_ast_nodes(
        test_case: tc.TestCase,
        variable_names: stmt_to_ast.NamingScope,
        modules_aliases: stmt_to_ast.NamingScope,
    ) -> List[ast.stmt]:
        """Transforms the given test case into a list of ast nodes."""
        visitor = stmt_to_ast.StatementToAstVisitor(modules_aliases, variable_names)
        for statement in test_case.statements:
            statement.accept(visitor)
        return visitor.ast_nodes

    @staticmethod
    def _wrap_node_in_module(node: ast.stmt) -> ast.Module:
        """Wraps the given node in a module, so that it can be executed."""
        ast.fix_missing_locations(node)
        wrapper = ast.parse("")
        wrapper.body = [node]
        return wrapper

    @staticmethod
    def _prepare_global_namespace(
        modules_aliases: stmt_to_ast.NamingScope,
    ) -> Dict[str, Any]:
        """
        Provides the required modules under the given aliases.
        :param modules_aliases:
        :return: a dict of module aliases and the corresponding module.
        """
        global_namespace: Dict[str, Any] = {}
        for required_module in modules_aliases.known_name_indices:
            global_namespace[modules_aliases.get_name(required_module)] = sys.modules[
                required_module
            ]
        return global_namespace
