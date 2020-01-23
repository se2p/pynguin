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
import logging
from typing import Tuple, Union, Any, List

import astor

import pynguin.testcase.testcase as tc
import pynguin.testcase.statement_to_ast as stmt_to_ast
from pynguin.utils.proxy import MagicProxy


def _recording_isinstance(
    obj: Any, obj_type: Union[type, Tuple[Union[type, tuple], ...]]
) -> bool:
    if isinstance(obj, MagicProxy):
        # pylint: disable=protected-access
        obj._instance_check_type = obj_type  # type: ignore
    return isinstance(obj, obj_type)


# pylint: disable=too-few-public-methods
class Executor:
    """An executor that executes the generated sequences."""

    _logger = logging.getLogger(__name__)

    def execute(self, test_case: tc.TestCase) -> bool:
        """Executes the statements in a test case.

        The return value indicates, whether or not the execution was successful,
        i.e., whether or not any unexpected exceptions were thrown.

        :param test_case: The test case that shall be executed
        :return: Whether or not the execution was successful
        """
        # TODO(fk) wrap new values in magic proxy.
        local_namespace = {}

        # TODO(fk) Provide required global stuff/modules.
        # TODO(fk) Provide capabilities to add instrumentation/tracing
        global_namespace = {}
        for node in self._to_ast_nodes(test_case):
            try:
                co = compile(self._wrap_node_in_module(node), "<ast>", 'exec')
                exec(co, global_namespace, local_namespace)
            except Exception as err:
                failed_stmt = astor.to_source(node)
                Executor._logger.warning(f"Failed to execute statement\n{failed_stmt}{err.args}")
                return False
        return True
        # TODO(fk) Provide ExecutionResult with more information(coverage, fitness, etc.), not just True/False

    @staticmethod
    def _to_ast_nodes(test_case: tc.TestCase) -> List[ast.AST]:
        """Transforms the given test case into a list of ast nodes."""
        naming_scope = stmt_to_ast.NamingScope()
        visitor = stmt_to_ast.StatementToAstVisitor(naming_scope)
        for statement in test_case.statements:
            statement.accept(visitor)
        return visitor.ast_nodes

    @staticmethod
    def _wrap_node_in_module(node: ast.AST) -> ast.Module:
        """Wraps the given node in a Module, so that it can be executed."""
        ast.fix_missing_locations(node)
        wrapper = ast.parse("")
        wrapper.body = [node]
        return wrapper
