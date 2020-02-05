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
"""Provides a visitor that transforms statements to ast"""
from __future__ import annotations

import ast
from typing import List, Dict, Any

import pynguin.testcase.statements.assignmentstatement as assign_stmt
import pynguin.testcase.statements.fieldstatement as field_stmt
import pynguin.testcase.statements.parametrizedstatements as param_stmt
import pynguin.testcase.statements.primitivestatements as prim_stmt
import pynguin.testcase.statements.statementvisitor as sv
import pynguin.testcase.variable.variablereference as vr


class NamingScope:
    """
    Maps any object to unique, human friendly names.
    """

    def __init__(self, prefix: str = "var"):
        """
        :param prefix: The prefix that will be used in the name.
        """
        self._next_index = 0
        self._known_name_indices: Dict[Any, int] = {}
        self._prefix = prefix

    def get_name(self, obj: Any) -> str:
        """
        Get the name for the given object within this scope.
        :param obj: the object for which a name is requested
        :return: the variable name
        """
        if obj in self._known_name_indices:
            index = self._known_name_indices.get(obj)
        else:
            index = self._next_index
            self._known_name_indices[obj] = index
            self._next_index += 1
        return self._prefix + str(index)

    @property
    def known_name_indices(self) -> Dict[Any, int]:
        """Provides a dict of objects and their corresponding variable name."""
        return self._known_name_indices


class StatementToAstVisitor(sv.StatementVisitor):
    """Visitor that transforms statements into a list of AST nodes."""

    def __init__(self, module_aliases: NamingScope, variable_names: NamingScope):
        self._ast_nodes: List[ast.stmt] = []
        self._variable_names = variable_names
        self._module_aliases = module_aliases

    @property
    def ast_nodes(self) -> List[ast.stmt]:
        """Get the list of generated AST nodes."""
        return self._ast_nodes

    def visit_int_primitive_statement(
        self, stmt: prim_stmt.IntPrimitiveStatement
    ) -> None:
        self._ast_nodes.append(self._create_numeric(stmt))

    def visit_float_primitive_statement(
        self, stmt: prim_stmt.FloatPrimitiveStatement
    ) -> None:
        self._ast_nodes.append(self._create_numeric(stmt))

    def visit_string_primitive_statement(
        self, stmt: prim_stmt.StringPrimitiveStatement
    ) -> None:
        self._ast_nodes.append(
            ast.Assign(
                targets=[self._create_var_name(stmt.return_value, False)],
                value=ast.Str(s=stmt.value),
            )
        )

    def visit_boolean_primitive_statement(
        self, stmt: prim_stmt.BooleanPrimitiveStatement
    ) -> None:
        self._ast_nodes.append(
            ast.Assign(
                targets=[self._create_var_name(stmt.return_value, False)],
                value=ast.NameConstant(value=stmt.value),
            )
        )

    def visit_none_statement(self, stmt: prim_stmt.NoneStatement) -> None:
        self._ast_nodes.append(
            ast.Assign(
                targets=[self._create_var_name(stmt.return_value, False)],
                value=ast.NameConstant(value=None),
            )
        )

    def visit_constructor_statement(
        self, stmt: param_stmt.ConstructorStatement
    ) -> None:
        assert stmt.constructor.owner
        self._ast_nodes.append(
            ast.Assign(
                targets=[self._create_var_name(stmt.return_value, False)],
                value=ast.Call(
                    func=ast.Attribute(
                        attr=stmt.constructor.owner.__name__,
                        ctx=ast.Load(),
                        value=self._create_module_alias(
                            stmt.constructor.owner.__module__
                        ),
                    ),
                    args=self._create_args(stmt),
                    keywords=self._create_kw_args(stmt),
                ),
            )
        )

    def visit_method_statement(self, stmt: param_stmt.MethodStatement) -> None:
        self._ast_nodes.append(
            ast.Assign(
                targets=[self._create_var_name(stmt.return_value, False)],
                value=ast.Call(
                    func=ast.Attribute(
                        attr=stmt.method.name,
                        ctx=ast.Load(),
                        value=self._create_var_name(stmt.callee, True),
                    ),
                    args=self._create_args(stmt),
                    keywords=self._create_kw_args(stmt),
                ),
            )
        )

    def visit_function_statement(self, stmt: param_stmt.FunctionStatement) -> None:
        self._ast_nodes.append(
            ast.Assign(
                targets=[self._create_var_name(stmt.return_value, False)],
                value=ast.Call(
                    func=ast.Attribute(
                        attr=stmt.function.name,
                        ctx=ast.Load(),
                        value=self._create_module_alias(stmt.function.__module__),
                    ),
                    args=self._create_args(stmt),
                    keywords=self._create_kw_args(stmt),
                ),
            )
        )

    def visit_field_statement(self, stmt: field_stmt.FieldStatement) -> None:
        self._ast_nodes.append(
            ast.Assign(
                targets=[
                    ast.Name(
                        id=self._variable_names.get_name(stmt.return_value),
                        ctx=ast.Store(),
                    )
                ],
                value=ast.Attribute(
                    attr=stmt.field,
                    ctx=ast.Load(),
                    value=self._create_var_name(stmt.source, True),
                ),
            )
        )

    def visit_assignment_statement(self, stmt: assign_stmt.AssignmentStatement) -> None:
        self._ast_nodes.append(
            ast.Assign(
                targets=[self._create_var_name(stmt.return_value, False)],
                value=self._create_var_name(stmt.rhs, True),
            )
        )

    def _create_numeric(self, stmt: prim_stmt.PrimitiveStatement) -> ast.stmt:
        """
        Small helper for int and float.
        """
        return ast.Assign(
            targets=[self._create_var_name(stmt.return_value, False)],
            value=ast.Num(n=stmt.value),
        )

    def _create_args(self, stmt: param_stmt.ParametrizedStatement) -> List[ast.Name]:
        """Creates the positional arguments."""
        args = []
        for arg in stmt.args:
            args.append(self._create_var_name(arg, True))
        return args

    def _create_kw_args(
        self, stmt: param_stmt.ParametrizedStatement
    ) -> List[ast.keyword]:
        """Creates the keyword arguments."""
        kwargs = []
        for name, value in stmt.kwargs.items():
            kwargs.append(
                ast.keyword(arg=name, value=self._create_var_name(value, True),)
            )
        return kwargs

    def _create_var_name(self, var: vr.VariableReference, load: bool) -> ast.Name:
        """
        Create a name node for the corresponding variable.
        :param var: the variable reference
        :param load: load or store?
        :return: the name node
        """
        return ast.Name(
            id=self._variable_names.get_name(var),
            ctx=ast.Load() if load else ast.Store(),
        )

    def _create_module_alias(self, module_name) -> ast.Name:
        """Create a name node for a module alias."""
        return ast.Name(id=self._module_aliases.get_name(module_name), ctx=ast.Load())
