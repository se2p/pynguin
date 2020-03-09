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
"""Provides an abstract executor as a base class for various executors."""
import ast
import sys
from abc import ABCMeta, abstractmethod
from typing import Generic, TypeVar, List, Dict, Any

import pynguin.testcase.statement_to_ast as stmt_to_ast
import pynguin.testcase.testcase as tc
import pynguin.testsuite.testsuitechromosome as tsc

T = TypeVar("T")  # pylint: disable=invalid-name


class AbstractExecutor(Generic[T], metaclass=ABCMeta):
    """An abstract executor that executes the generated test cases."""

    def __init__(self) -> None:
        self._local_namespace: Dict[str, Any] = {}
        self._variable_names = stmt_to_ast.NamingScope()
        self._modules_aliases = stmt_to_ast.NamingScope(prefix="module")
        self._ast_nodes: List[ast.stmt] = []
        self._global_namespace: Dict[str, Any] = {}

    @abstractmethod
    def execute(self, test_case: tc.TestCase) -> T:
        """Executes the statements in a test case.

        :param test_case: The test case that shall be executed
        :return: Result of the execution
        """

    @abstractmethod
    def execute_test_suite(self, test_suite: tsc.TestSuiteChromosome) -> T:
        """Executes all statements of all test cases in a test suite.

        :param test_suite: The list of test cases, i.e., test test suite
        :return: Result of the execution
        """

    @staticmethod
    def to_ast_nodes(
        test_case: tc.TestCase,
        variable_names: stmt_to_ast.NamingScope,
        modules_aliases: stmt_to_ast.NamingScope,
    ) -> List[ast.stmt]:
        """Transforms the given test case into a list of ast nodes.

        :param test_case: The current test case
        :param variable_names: The scope of the variable names
        :param modules_aliases: The cope of the module alias names
        :return: A list of ast nodes
        """
        visitor = stmt_to_ast.StatementToAstVisitor(modules_aliases, variable_names)
        for statement in test_case.statements:
            statement.accept(visitor)
        return visitor.ast_nodes

    @staticmethod
    def wrap_node_in_module(node: ast.stmt) -> ast.Module:
        """Wraps the given node in a module, such that it can be executed.

        :param node: The node to wrap
        :return: The module wrapping the node
        """
        ast.fix_missing_locations(node)
        wrapper = ast.parse("")
        wrapper.body = [node]
        return wrapper

    @staticmethod
    def prepare_global_namespace(
        modules_aliases: stmt_to_ast.NamingScope,
    ) -> Dict[str, Any]:
        """Provides the required modules under the given aliases.

        :param modules_aliases: The module aliases
        :return: A dictionary of module aliases and the corresponding module
        """
        global_namespace: Dict[str, Any] = {}
        for required_module in modules_aliases.known_name_indices:
            global_namespace[modules_aliases.get_name(required_module)] = sys.modules[
                required_module
            ]
        return global_namespace

    def setup(self, test_case: tc.TestCase) -> None:
        """Setup the internal state of the executor to execute a test case

        :param test_case: The test case to be executed
        """
        self._local_namespace = {}
        self._variable_names = stmt_to_ast.NamingScope()
        self._modules_aliases = stmt_to_ast.NamingScope(prefix="module")
        self._ast_nodes = self.to_ast_nodes(
            test_case, self._variable_names, self._modules_aliases
        )
        self._global_namespace = self.prepare_global_namespace(self._modules_aliases)
