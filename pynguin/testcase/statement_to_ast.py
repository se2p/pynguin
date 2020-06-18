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
from typing import List

import pynguin.testcase.statements.assignmentstatement as assign_stmt
import pynguin.testcase.statements.fieldstatement as field_stmt
import pynguin.testcase.statements.parametrizedstatements as param_stmt
import pynguin.testcase.statements.primitivestatements as prim_stmt
import pynguin.testcase.statements.statementvisitor as sv
import pynguin.testcase.variable.variablereference as vr
from pynguin.utils.namingscope import NamingScope


class StatementToAstVisitor(sv.StatementVisitor):
    """Visitor that transforms statements into a list of AST nodes."""

    def __init__(
        self,
        module_aliases: NamingScope,
        variable_names: NamingScope,
        wrap_nodes: bool = False,
    ) -> None:
        """Creates a new transformation visitor that transforms our internal
        statements to Python AST nodes.

        Args:
            module_aliases: A naming scope for module alias names
            variable_names: A naming scope for variable names
            wrap_nodes: If True, wrap the create AST nodes in a try-except block
        """
        self._ast_nodes: List[ast.stmt] = []
        self._variable_names = variable_names
        self._module_aliases = module_aliases
        self._wrap_nodes = wrap_nodes

    @property
    def ast_nodes(self) -> List[ast.stmt]:
        """Get the list of generated AST nodes.

        In case the `wrap_nodes` property was set, the nodes will be wrapped in
        ```
        try:
            [nodes]
        except BaseException:
            pass
        ```

        Returns:
            A list of AST nodes
        """
        if self._wrap_nodes:
            nodes: List[ast.stmt] = [
                ast.Try(
                    body=self._ast_nodes,
                    handlers=[
                        ast.ExceptHandler(
                            body=[ast.Pass()],
                            name=None,
                            type=ast.Name(ctx=ast.Load(), id="BaseException"),
                        )
                    ],
                    orelse=[],
                    finalbody=[],
                )
            ]
            return nodes
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
        owner = stmt.accessible_object().owner
        assert owner
        self._ast_nodes.append(
            ast.Assign(
                targets=[self._create_var_name(stmt.return_value, False)],
                value=ast.Call(
                    func=ast.Attribute(
                        attr=owner.__name__,
                        ctx=ast.Load(),
                        value=self._create_module_alias(owner.__module__),
                    ),
                    args=self._create_args(stmt),
                    keywords=self._create_kw_args(stmt),
                ),
            )
        )

    def visit_method_statement(self, stmt: param_stmt.MethodStatement) -> None:
        call = ast.Call(
            func=ast.Attribute(
                attr=stmt.accessible_object().callable.__name__,
                ctx=ast.Load(),
                value=self._create_var_name(stmt.callee, True),
            ),
            args=self._create_args(stmt),
            keywords=self._create_kw_args(stmt),
        )
        if stmt.return_value.is_none_type():
            node: ast.stmt = ast.Expr(value=call)
        else:
            node = ast.Assign(
                targets=[self._create_var_name(stmt.return_value, False)], value=call,
            )
        self._ast_nodes.append(node)

    def visit_function_statement(self, stmt: param_stmt.FunctionStatement) -> None:
        call = ast.Call(
            func=ast.Attribute(
                attr=stmt.accessible_object().callable.__name__,
                ctx=ast.Load(),
                value=self._create_module_alias(
                    stmt.accessible_object().callable.__module__
                ),
            ),
            args=self._create_args(stmt),
            keywords=self._create_kw_args(stmt),
        )
        if stmt.return_value.is_none_type():
            node: ast.stmt = ast.Expr(value=call)
        else:
            node = ast.Assign(
                targets=[self._create_var_name(stmt.return_value, False)], value=call,
            )
        self._ast_nodes.append(node)

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
        """Small helper for int and float.

        Args:
            stmt: The primitive statement

        Returns:
            The matching AST statement
        """
        return ast.Assign(
            targets=[self._create_var_name(stmt.return_value, False)],
            value=ast.Num(n=stmt.value),
        )

    def _create_args(self, stmt: param_stmt.ParametrizedStatement) -> List[ast.Name]:
        """Creates the positional arguments.

        Args:
            stmt: The parameterised statement

        Returns:
            A list of AST statements
        """
        args = []
        for arg in stmt.args:
            args.append(self._create_var_name(arg, True))
        return args

    def _create_kw_args(
        self, stmt: param_stmt.ParametrizedStatement
    ) -> List[ast.keyword]:
        """Creates the keyword arguments.

        Args:
            stmt: The parameterised statement

        Returns:
            A list of AST statements
        """
        kwargs = []
        for name, value in stmt.kwargs.items():
            kwargs.append(
                ast.keyword(arg=name, value=self._create_var_name(value, True),)
            )
        return kwargs

    def _create_var_name(self, var: vr.VariableReference, load: bool) -> ast.Name:
        """Create a name node for the corresponding variable.

        Args:
            var: the variable reference
            load: load or store?

        Returns:
            the name node
        """
        return ast.Name(
            id=self._variable_names.get_name(var),
            ctx=ast.Load() if load else ast.Store(),
        )

    def _create_module_alias(self, module_name) -> ast.Name:
        """Create a name node for a module alias.

        Args:
            module_name: The name of the module

        Returns:
            An AST statement
        """
        return ast.Name(id=self._module_aliases.get_name(module_name), ctx=ast.Load())
