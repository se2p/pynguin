#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides a visitor that transforms statements to AST."""

from __future__ import annotations

import ast

from inspect import Parameter
from typing import TYPE_CHECKING
from typing import Any
from typing import cast

import pynguin.utils.ast_util as au

from pynguin.testcase.statement import ASTAssignStatement
from pynguin.testcase.statement import ClassPrimitiveStatement
from pynguin.testcase.statement import StatementVisitor


if TYPE_CHECKING:
    import pynguin.utils.namingscope as ns

    from pynguin.testcase.statement import AllowedValuesStatement
    from pynguin.testcase.statement import AssignmentStatement
    from pynguin.testcase.statement import BooleanPrimitiveStatement
    from pynguin.testcase.statement import BytesPrimitiveStatement
    from pynguin.testcase.statement import ComplexPrimitiveStatement
    from pynguin.testcase.statement import ConstructorStatement
    from pynguin.testcase.statement import DictStatement
    from pynguin.testcase.statement import EnumPrimitiveStatement
    from pynguin.testcase.statement import FieldStatement
    from pynguin.testcase.statement import FloatPrimitiveStatement
    from pynguin.testcase.statement import FunctionStatement
    from pynguin.testcase.statement import IntPrimitiveStatement
    from pynguin.testcase.statement import ListStatement
    from pynguin.testcase.statement import MethodStatement
    from pynguin.testcase.statement import NdArrayStatement
    from pynguin.testcase.statement import NoneStatement
    from pynguin.testcase.statement import ParametrizedStatement
    from pynguin.testcase.statement import PrimitiveStatement
    from pynguin.testcase.statement import SetStatement
    from pynguin.testcase.statement import StringPrimitiveStatement
    from pynguin.testcase.statement import TupleStatement
    from pynguin.utils.generic.genericaccessibleobject import (
        GenericCallableAccessibleObject,
    )


class StatementToAstVisitor(StatementVisitor):  # noqa: PLR0904
    """Visitor that transforms statements into a list of AST nodes."""

    def __init__(
        self,
        module_aliases: ns.AbstractNamingScope,
        variable_names: ns.AbstractNamingScope,
        *,
        store_call_return: bool = True,
    ) -> None:
        """Creates a new transformation visitor.

        The visitor transforms our internal statements to Python AST nodes.

        Args:
            module_aliases: A naming scope for module alias names.
            variable_names: A naming scope for variable names.
            store_call_return: Should the result of a call be stored in a variable?
                For example, if we know that a call raises an exception, then we don't
                need to assign the result to a variable, as it will never be assigned
                anyway
        """
        self._ast_node: ast.stmt | None = None
        self._variable_names = variable_names
        self._module_aliases = module_aliases
        self._store_call_return = store_call_return

    @property
    def ast_node(self) -> ast.stmt:
        """Provide the generated ast statement.

        Returns:
            the generated ast statement
        """
        assert self._ast_node, "No statement visited"
        return self._ast_node

    def visit_int_primitive_statement(  # noqa: D102
        self, stmt: IntPrimitiveStatement
    ) -> None:
        self._ast_node = self._create_constant(stmt)

    def visit_float_primitive_statement(  # noqa: D102
        self, stmt: FloatPrimitiveStatement
    ) -> None:
        self._ast_node = self._create_constant(stmt)

    def visit_complex_primitive_statement(  # noqa: D102
        self, stmt: ComplexPrimitiveStatement
    ) -> None:
        self._ast_node = self._create_constant(stmt)

    def visit_string_primitive_statement(  # noqa: D102
        self, stmt: StringPrimitiveStatement
    ) -> None:
        self._ast_node = self._create_constant(stmt)

    def visit_bytes_primitive_statement(  # noqa: D102
        self, stmt: BytesPrimitiveStatement
    ) -> None:
        self._ast_node = self._create_constant(stmt)

    def visit_boolean_primitive_statement(  # noqa: D102
        self, stmt: BooleanPrimitiveStatement
    ) -> None:
        self._ast_node = self._create_constant(stmt)

    def visit_enum_statement(self, stmt: EnumPrimitiveStatement) -> None:  # noqa: D102
        owner = stmt.accessible_object().owner
        assert owner
        self._ast_node = ast.Assign(
            targets=[
                au.create_full_name(
                    self._variable_names, self._module_aliases, stmt.ret_val, load=False
                )
            ],
            value=ast.Attribute(
                value=ast.Attribute(
                    value=self._create_module_alias(owner.module),
                    attr=owner.name,
                    ctx=ast.Load(),
                ),
                attr=stmt.value_name,
                ctx=ast.Load(),
            ),
        )

    def visit_class_primitive_statement(  # noqa: D102
        self, stmt: ClassPrimitiveStatement
    ) -> None:
        clazz = stmt.type_info
        self._ast_node = ast.Assign(
            targets=[
                au.create_full_name(
                    self._variable_names, self._module_aliases, stmt.ret_val, load=False
                )
            ],
            # TODO(fk) think about nested classes, also for enums.
            value=ast.Attribute(
                value=self._create_module_alias(clazz.module),
                attr=clazz.name,
                ctx=ast.Load(),
            ),
        )

    def visit_none_statement(self, stmt: NoneStatement) -> None:  # noqa: D102
        self._ast_node = self._create_constant(stmt)

    def visit_constructor_statement(  # noqa: D102
        self, stmt: ConstructorStatement
    ) -> None:
        owner = stmt.accessible_object().owner
        assert owner
        args, kwargs = self._create_args(stmt)
        call = ast.Call(
            func=ast.Attribute(
                attr=owner.name,
                ctx=ast.Load(),
                value=self._create_module_alias(owner.module),
            ),
            args=args,
            keywords=kwargs,
        )
        if self._store_call_return:
            self._ast_node = ast.Assign(
                targets=[
                    au.create_full_name(
                        self._variable_names,
                        self._module_aliases,
                        stmt.ret_val,
                        load=False,
                    )
                ],
                value=call,
            )
        else:
            self._ast_node = ast.Expr(value=call)

    def visit_method_statement(self, stmt: MethodStatement) -> None:  # noqa: D102
        args, kwargs = self._create_args(stmt)
        call = ast.Call(
            func=ast.Attribute(
                attr=stmt.accessible_object().callable.__name__,
                ctx=ast.Load(),
                value=au.create_full_name(
                    self._variable_names, self._module_aliases, stmt.callee, load=True
                ),
            ),
            args=args,
            keywords=kwargs,
        )
        if not self._store_call_return:
            self._ast_node = ast.Expr(value=call)
        else:
            self._ast_node = ast.Assign(
                targets=[
                    au.create_full_name(
                        self._variable_names,
                        self._module_aliases,
                        stmt.ret_val,
                        load=False,
                    )
                ],
                value=call,
            )

    def visit_function_statement(self, stmt: FunctionStatement) -> None:  # noqa: D102
        args, kwargs = self._create_args(stmt)
        call = ast.Call(
            func=ast.Attribute(
                attr=stmt.accessible_object().callable.__name__,
                ctx=ast.Load(),
                value=self._create_module_alias(stmt.accessible_object().callable.__module__),
            ),
            args=args,
            keywords=kwargs,
        )
        if not self._store_call_return:
            self._ast_node = ast.Expr(value=call)
        else:
            self._ast_node = ast.Assign(
                targets=[
                    au.create_full_name(
                        self._variable_names,
                        self._module_aliases,
                        stmt.ret_val,
                        load=False,
                    )
                ],
                value=call,
            )

    def visit_field_statement(self, stmt: FieldStatement) -> None:  # noqa: D102
        self._ast_node = ast.Assign(
            targets=[
                ast.Name(
                    id=self._variable_names.get_name(stmt.ret_val),
                    ctx=ast.Store(),
                )
            ],
            value=ast.Attribute(
                attr=stmt.field.field,
                ctx=ast.Load(),
                value=au.create_full_name(
                    self._variable_names, self._module_aliases, stmt.source, load=True
                ),
            ),
        )

    def visit_assignment_statement(  # noqa: D102
        self, stmt: AssignmentStatement
    ) -> None:
        self._ast_node = ast.Assign(
            targets=[
                au.create_full_name(
                    self._variable_names, self._module_aliases, stmt.lhs, load=False
                )
            ],
            value=au.create_full_name(
                self._variable_names, self._module_aliases, stmt.rhs, load=True
            ),
        )

    def visit_ast_assign_statement(  # noqa: D102
        self, stmt: ASTAssignStatement
    ) -> None:
        self._ast_node = ast.Assign(
            targets=[
                au.create_full_name(
                    self._variable_names, self._module_aliases, stmt.ret_val, load=False
                )
            ],
            value=stmt.get_rhs_as_normal_ast(  # type: ignore[arg-type]
                lambda x: au.create_full_name(
                    self._variable_names, self._module_aliases, x, load=True
                )
            ),
        )

    def visit_list_statement(self, stmt: ListStatement) -> None:  # noqa: D102
        self._ast_node = ast.Assign(
            targets=[
                au.create_full_name(
                    self._variable_names, self._module_aliases, stmt.ret_val, load=False
                )
            ],
            value=ast.List(
                elts=[
                    au.create_full_name(self._variable_names, self._module_aliases, x, load=True)
                    for x in stmt.elements
                ],
                ctx=ast.Load(),
            ),
        )

    def visit_ndarray_statement(self, stmt: NdArrayStatement) -> None:  # noqa: D102
        self._ast_node = ast.Assign(
            targets=[
                au.create_full_name(
                    self._variable_names, self._module_aliases, stmt.ret_val, load=False
                )
            ],
            value=au.create_ast_for_nested_list(stmt.elements),
        )

    def visit_allowed_values_statement(self, stmt: AllowedValuesStatement) -> None:  # noqa: D102
        self._ast_node = self._create_constant(stmt)

    def visit_set_statement(self, stmt: SetStatement) -> None:  # noqa: D102
        # There is no literal for empty sets, so we have to write "set()"
        inner: Any
        if len(stmt.elements) == 0:
            inner = ast.Call(func=ast.Name(id="set", ctx=ast.Load()), args=[], keywords=[])
        else:
            inner = ast.Set(  # type: ignore[call-arg]
                elts=[
                    au.create_full_name(self._variable_names, self._module_aliases, x, load=True)
                    for x in stmt.elements
                ],
                ctx=ast.Load(),
            )

        self._ast_node = ast.Assign(
            targets=[
                au.create_full_name(
                    self._variable_names, self._module_aliases, stmt.ret_val, load=False
                )
            ],
            value=inner,
        )

    def visit_tuple_statement(self, stmt: TupleStatement) -> None:  # noqa: D102
        self._ast_node = ast.Assign(
            targets=[
                au.create_full_name(
                    self._variable_names, self._module_aliases, stmt.ret_val, load=False
                )
            ],
            value=ast.Tuple(
                elts=[
                    au.create_full_name(self._variable_names, self._module_aliases, x, load=True)
                    for x in stmt.elements
                ],
                ctx=ast.Load(),
            ),
        )

    def visit_dict_statement(self, stmt: DictStatement) -> None:  # noqa: D102
        self._ast_node = ast.Assign(
            targets=[
                au.create_full_name(
                    self._variable_names, self._module_aliases, stmt.ret_val, load=False
                )
            ],
            value=ast.Dict(
                keys=[
                    au.create_full_name(self._variable_names, self._module_aliases, x[0], load=True)
                    for x in stmt.elements
                ],
                values=[
                    au.create_full_name(self._variable_names, self._module_aliases, x[1], load=True)
                    for x in stmt.elements
                ],
            ),
        )

    def _create_constant(self, stmt: PrimitiveStatement) -> ast.stmt:
        """All primitive values are constants.

        Args:
            stmt: The primitive statement

        Returns:
            The matching AST statement
        """
        return ast.Assign(
            targets=[
                au.create_full_name(
                    self._variable_names, self._module_aliases, stmt.ret_val, load=False
                )
            ],
            value=ast.Constant(value=stmt.value),
        )

    def _create_args(self, stmt: ParametrizedStatement) -> tuple[list[ast.expr], list[ast.keyword]]:
        """Creates the AST nodes for arguments.

        Creates the positional arguments, i.e., POSITIONAL_ONLY,
        POSITIONAL_OR_KEYWORD and VAR_POSITIONAL as well as the keyword arguments,
        i.e., KEYWORD_ONLY or VAR_KEYWORD.

        Args:
            stmt: The parameterised statement

        Returns:
            Two lists of AST statements, one for args and one for kwargs
        """
        args: list[ast.expr] = []
        kwargs = []

        gen_callable: GenericCallableAccessibleObject = cast(
            "GenericCallableAccessibleObject", stmt.accessible_object()
        )

        left_of_current: list[str] = []

        parameters = gen_callable.inferred_signature.signature.parameters

        for param_name, param in parameters.items():
            if param_name in stmt.args:
                # The variable that is passed in as an argument
                var = au.create_full_name(
                    self._variable_names,
                    self._module_aliases,
                    stmt.args[param_name],
                    load=True,
                )
                match param.kind:
                    case Parameter.POSITIONAL_ONLY:
                        args.append(var)
                    case Parameter.POSITIONAL_OR_KEYWORD:
                        # If a POSITIONAL_OR_KEYWORD parameter left of the current param
                        # has a default, and we did not pass a value, we must pass the
                        # current value by keyword, otherwise by position.
                        if any(
                            parameters[left].default is not Parameter.empty
                            and left not in stmt.args
                            for left in left_of_current
                        ):
                            kwargs.append(
                                ast.keyword(
                                    arg=param_name,
                                    value=var,
                                )
                            )
                        else:
                            args.append(var)
                    case Parameter.KEYWORD_ONLY:
                        kwargs.append(
                            ast.keyword(
                                arg=param_name,
                                value=var,
                            )
                        )
                    case Parameter.VAR_POSITIONAL:
                        # Append *args, if necessary.
                        args.append(
                            ast.Starred(
                                value=var,
                                ctx=ast.Load(),
                            )
                        )
                    case Parameter.VAR_KEYWORD:
                        # Append **kwargs, if necessary.
                        kwargs.append(
                            ast.keyword(
                                arg=None,
                                value=var,
                            )
                        )
            left_of_current.append(param_name)
        return args, kwargs

    def _create_module_alias(self, module_name) -> ast.Name:
        """Create a name node for a module alias.

        Args:
            module_name: The name of the module

        Returns:
            An AST statement
        """
        return ast.Name(id=self._module_aliases.get_name(module_name), ctx=ast.Load())
