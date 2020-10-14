#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
"""Provides an execution context that can be used when executing test cases."""
import ast
import sys
from types import ModuleType
from typing import Any, Dict, Optional

import pynguin.testcase.statement_to_ast as stmt_to_ast
import pynguin.testcase.statements.statement as stmt
import pynguin.testcase.variable.variablereference as vr
from pynguin.utils.namingscope import NamingScope


class ExecutionContext:
    """Contains information required in the context of an execution.
    e.g. the used variables, modules and
    the AST representation of the statements that should be executed."""

    def __init__(self) -> None:
        """Create new execution context."""
        self._local_namespace: Dict[str, Any] = {}
        self._variable_names = NamingScope()
        self._modules_aliases = NamingScope(prefix="module")
        self._global_namespace: Dict[str, ModuleType] = {}

    @property
    def local_namespace(self) -> Dict[str, Any]:
        """The local namespace.

        Returns:
            The local namespace
        """
        return self._local_namespace

    def get_variable_value(self, variable: vr.VariableReference) -> Optional[Any]:
        """Returns the value that is assigned to the given variable in the local namespace, if any.

        Args:
            variable: the variable whose value we want

        Returns: the assigned value or None.
        """
        if variable in self._variable_names.known_name_indices:
            name = self._variable_names.get_name(variable)
            if name in self._local_namespace:
                return self._local_namespace.get(name)
        return None

    @property
    def global_namespace(self) -> Dict[str, ModuleType]:
        """The global namespace.

        Returns:
            The global namespace
        """
        return self._global_namespace

    def executable_node_for(
        self,
        statement: stmt.Statement,
    ) -> ast.Module:
        """Transforms the given statement in an executable ast node.

        Args:
            statement: The statement that should be converted.

        Returns:
            An executable ast node.
        """
        modules_before = len(self._modules_aliases.known_name_indices)
        visitor = stmt_to_ast.StatementToAstVisitor(
            self._modules_aliases, self._variable_names
        )
        statement.accept(visitor)
        if modules_before != len(self._modules_aliases.known_name_indices):
            # new module added
            # TODO(fk) cleaner solution?
            self._global_namespace = ExecutionContext._create_global_namespace(
                self._modules_aliases
            )
        assert (
            len(visitor.ast_nodes) == 1
        ), "Expected statement to produce exactly one ast node"
        return ExecutionContext._wrap_node_in_module(visitor.ast_nodes[0])

    @staticmethod
    def _wrap_node_in_module(node: ast.stmt) -> ast.Module:
        """Wraps the given node in a module, such that it can be executed.

        Args:
            node: The node to wrap

        Returns:
            The module wrapping the node
        """
        ast.fix_missing_locations(node)
        return ast.Module(body=[node], type_ignores=[])

    @staticmethod
    def _create_global_namespace(
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
