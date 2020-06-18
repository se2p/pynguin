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
"""Provides an execution context that can be used when executing test cases."""
import ast
import sys
from types import ModuleType
from typing import Any, Dict, Iterator, List

import pynguin.testcase.statement_to_ast as stmt_to_ast
import pynguin.testcase.testcase as tc
from pynguin.utils.namingscope import NamingScope


class ExecutionContext:
    """Contains information required in the context of an execution.
    e.g. the used variables, modules and
    the AST representation of the statements that should be executed."""

    def __init__(self, test_case: tc.TestCase) -> None:
        """Create new execution context for the given test case.

        Args:
            test_case: the executed test case
        """
        self._local_namespace: Dict[str, Any] = dict()
        self._variable_names = NamingScope()
        self._modules_aliases = NamingScope(prefix="module")
        self._ast_nodes = self._to_ast_nodes(
            test_case, self._variable_names, self._modules_aliases
        )
        self._global_namespace = self._prepare_global_namespace(self._modules_aliases)

    @property
    def local_namespace(self) -> Dict[str, Any]:
        """The local namespace.

        Returns:
            The local namespace
        """
        return self._local_namespace

    @property
    def global_namespace(self) -> Dict[str, ModuleType]:
        """The global namespace.

        Returns:
            The global namespace
        """
        return self._global_namespace

    def executable_nodes(self) -> Iterator[ast.Module]:
        """An iterator that generates executable nodes on demand

        Yields:
            An iterator over the executable AST nodes
        """
        for node in self._ast_nodes:
            yield ExecutionContext._wrap_node_in_module(node)

    @staticmethod
    def _to_ast_nodes(
        test_case: tc.TestCase,
        variable_names: NamingScope,
        modules_aliases: NamingScope,
    ) -> List[ast.stmt]:
        """Transforms the given test case into a list of ast nodes.

        Args:
            test_case: The current test case
            variable_names: The scope of the variable names
            modules_aliases: The cope of the module alias names

        Returns:
            A list of ast nodes
        """
        visitor = stmt_to_ast.StatementToAstVisitor(modules_aliases, variable_names)
        for statement in test_case.statements:
            statement.accept(visitor)
        return visitor.ast_nodes

    @staticmethod
    def _wrap_node_in_module(node: ast.stmt) -> ast.Module:
        """Wraps the given node in a module, such that it can be executed.

        Args:
            node: The node to wrap

        Returns:
            The module wrapping the node
        """
        ast.fix_missing_locations(node)
        wrapper = ast.parse("")
        wrapper.body = [node]
        return wrapper

    @staticmethod
    def _prepare_global_namespace(
        modules_aliases: NamingScope,
    ) -> Dict[str, ModuleType]:
        """Provides the required modules under the given aliases.

        Args:
            modules_aliases: The module aliases

        Returns:
            A dictionary of module aliases and the corresponding module
        """
        global_namespace: Dict[str, ModuleType] = {}
        for required_module in modules_aliases.known_name_indices:
            global_namespace[modules_aliases.get_name(required_module)] = sys.modules[
                required_module
            ]
        return global_namespace
