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
import logging
import os
from typing import Tuple, Union, Any, List, Dict

import astor  # type: ignore

import pynguin.testcase.testcase as tc
import pynguin.testcase.statement_to_ast as stmt_to_ast
import pynguin.testcase.execution.executionresult as res
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
    """An executor that executes the generated sequences."""

    _logger = logging.getLogger(__name__)

    def execute(self, test_case: tc.TestCase) -> res.ExecutionResult:
        """Executes the statements in a test case.

        The return value indicates, whether or not the execution was successful,
        i.e., whether or not any unexpected exceptions were thrown.

        :param test_case: The test case that shall be executed
        :return: Result of the execution
        """
        result = res.ExecutionResult()

        # TODO(fk) wrap new values in magic proxy.
        local_namespace: Dict[str, Any] = {}

        # TODO(fk) Provide required global stuff/modules.
        # TODO(fk) Provide capabilities to add instrumentation/tracing
        global_namespace: Dict[str, Any] = {}
        with open(os.devnull, mode="w") as null_file:
            with contextlib.redirect_stdout(null_file):
                for idx, node in enumerate(self._to_ast_nodes(test_case)):
                    try:
                        code = compile(self._wrap_node_in_module(node), "<ast>", "exec")
                        # pylint: disable=exec-used
                        exec(code, global_namespace, local_namespace)
                    except Exception as err:  # pylint: disable=broad-except
                        failed_stmt = astor.to_source(node)
                        TestCaseExecutor._logger.warning(
                            "Failed to execute statement:\n%s%s", failed_stmt, err.args
                        )
                        result.report_new_thrown_exception(idx, err)
        return result
        # TODO(fk) Provide ExecutionResult with more information(coverage, fitness, etc.)

    @staticmethod
    def _to_ast_nodes(test_case: tc.TestCase) -> List[ast.stmt]:
        """Transforms the given test case into a list of ast nodes."""
        naming_scope = stmt_to_ast.NamingScope()
        visitor = stmt_to_ast.StatementToAstVisitor(naming_scope)
        for statement in test_case.statements:
            statement.accept(visitor)
        return visitor.ast_nodes

    @staticmethod
    def _wrap_node_in_module(node: ast.stmt) -> ast.Module:
        """Wraps the given node in a Module, so that it can be executed."""
        ast.fix_missing_locations(node)
        wrapper = ast.parse("")
        wrapper.body = [node]
        return wrapper
