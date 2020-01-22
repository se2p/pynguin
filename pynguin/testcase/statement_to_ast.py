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
from typing import List, Dict

import pynguin.testcase.statements.assignmentstatement as assign_stmt
import pynguin.testcase.statements.fieldstatement as field_stmt
import pynguin.testcase.statements.parametrizedstatements as param_stmt
import pynguin.testcase.statements.primitivestatements as prim_stmt
import pynguin.testcase.statements.statementvisitor as sv
import pynguin.testcase.variable.variablereference as vr


class NamingScope:
    """
    Provides variable names when transforming variable references.
    """

    def __init__(self):
        self._next_index = 0
        self._known_var_indices = {}

    def get_variable_name(self, var: vr.VariableReference) -> str:
        """
        Get the variable name for the given variable within this scope.
        :param var: the variable reference for which a name is requested
        :return: the variable name
        """
        if var in self._known_var_indices:
            index = self._known_var_indices.get(var)
        else:
            index = self._next_index
            self._known_var_indices[var] = index
            self._next_index += 1
        return "var" + str(index)

    @property
    def known_var_indices(self) -> Dict[vr.VariableReference, int]:
        """Provides a dict of variable references and there corresponding variable name"""
        return self._known_var_indices


class StatementToAstVisitor(sv.StatementVisitor):
    """Visitor that transforms statements into a list of AST nodes."""

    def __init__(self, scope: NamingScope):
        self._ast_nodes: List[ast.AST] = []
        self._scope = scope

    @property
    def ast_nodes(self) -> List[ast.AST]:
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
                targets=[
                    ast.Name(
                        id=self._scope.get_variable_name(stmt.return_value),
                        ctx=ast.Store(),
                    )
                ],
                value=ast.Str(s=stmt.value),
            )
        )

    def visit_boolean_primitive_statement(
        self, stmt: prim_stmt.BooleanPrimitiveStatement
    ) -> None:
        self._ast_nodes.append(
            ast.Assign(
                targets=[
                    ast.Name(
                        id=self._scope.get_variable_name(stmt.return_value),
                        ctx=ast.Store(),
                    )
                ],
                value=ast.NameConstant(value=stmt.value),
            )
        )

    def visit_constructor_statement(
        self, stmt: param_stmt.ConstructorStatement
    ) -> None:
        pass
        # TODO(fk)

    def visit_method_statement(self, stmt: param_stmt.MethodStatement) -> None:
        pass
        # TODO(fk)

    def visit_field_statement(self, stmt: field_stmt.FieldStatement) -> None:
        self._ast_nodes.append(
            ast.Assign(
                targets=[
                    ast.Name(
                        id=self._scope.get_variable_name(stmt.return_value),
                        ctx=ast.Store(),
                    )
                ],
                value=ast.Attribute(
                    attr=stmt.field,
                    ctx=ast.Load(),
                    value=ast.Name(
                        ctx=ast.Load(), id=self._scope.get_variable_name(stmt.source)
                    ),
                ),
            )
        )

    def visit_assignment_statement(self, stmt: assign_stmt.AssignmentStatement) -> None:
        self._ast_nodes.append(
            ast.Assign(
                targets=[
                    ast.Name(
                        id=self._scope.get_variable_name(stmt.return_value),
                        ctx=ast.Store(),
                    )
                ],
                value=ast.Name(
                    id=self._scope.get_variable_name(stmt.rhs), ctx=ast.Load(),
                ),
            )
        )

    def _create_numeric(self, stmt: prim_stmt.PrimitiveStatement) -> ast.AST:
        """
        Small helper for int and float.
        """
        return ast.Assign(
            targets=[
                ast.Name(
                    id=self._scope.get_variable_name(stmt.return_value),
                    ctx=ast.Store(),
                )
            ],
            value=ast.Num(n=stmt.value),
        )
