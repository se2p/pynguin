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
from ast import Module
from unittest.mock import MagicMock
import pynguin.testcase.statements.parametrizedstatements as param_stmt

import astor
import pytest

import pynguin.testcase.statement_to_ast as stmt_to_ast
import pynguin.testcase.variable.variablereference as vr
import pynguin.testcase.statements.statement as stmt


def test_naming_scope_same(variable_reference_mock):
    scope = stmt_to_ast.NamingScope()
    name1 = scope.get_variable_name(variable_reference_mock)
    name2 = scope.get_variable_name(variable_reference_mock)
    assert name1 == name2


def test_naming_scope_different(variable_reference_mock):
    scope = stmt_to_ast.NamingScope()
    name1 = scope.get_variable_name(variable_reference_mock)
    name2 = scope.get_variable_name(MagicMock(vr.VariableReference))
    assert name1 != name2


def test_naming_scope_known_indices_empty():
    scope = stmt_to_ast.NamingScope()
    assert scope.known_var_indices == {}


def test_naming_scope_known_indices_not_empty(variable_reference_mock):
    scope = stmt_to_ast.NamingScope()
    scope.get_variable_name(variable_reference_mock)
    assert scope.known_var_indices == {variable_reference_mock: 0}


@pytest.fixture()
def statement_to_ast_visitor() -> stmt_to_ast.StatementToAstVisitor:
    scope = stmt_to_ast.NamingScope()
    return stmt_to_ast.StatementToAstVisitor(scope)


def test_statement_to_ast_int(statement_to_ast_visitor):
    int_stmt = MagicMock(stmt.Statement)
    int_stmt.value = 5
    statement_to_ast_visitor.visit_int_primitive_statement(int_stmt)
    assert (
        astor.to_source(Module(body=statement_to_ast_visitor.ast_nodes)) == "var0 = 5\n"
    )


def test_statement_to_ast_float(statement_to_ast_visitor):
    float_stmt = MagicMock(stmt.Statement)
    float_stmt.value = 5.5
    statement_to_ast_visitor.visit_string_primitive_statement(float_stmt)
    assert (
        astor.to_source(Module(body=statement_to_ast_visitor.ast_nodes))
        == "var0 = 5.5\n"
    )


def test_statement_to_ast_str(statement_to_ast_visitor):
    str_stmt = MagicMock(stmt.Statement)
    str_stmt.value = "TestMe"
    statement_to_ast_visitor.visit_string_primitive_statement(str_stmt)
    assert (
        astor.to_source(Module(body=statement_to_ast_visitor.ast_nodes))
        == "var0 = 'TestMe'\n"
    )


def test_statement_to_ast_bool(statement_to_ast_visitor):
    bool_stmt = MagicMock(stmt.Statement)
    bool_stmt.value = True
    statement_to_ast_visitor.visit_string_primitive_statement(bool_stmt)
    assert (
        astor.to_source(Module(body=statement_to_ast_visitor.ast_nodes))
        == "var0 = True\n"
    )


def test_statement_to_ast_constructor_no_args(statement_to_ast_visitor, test_case_mock):
    constr_stmt = param_stmt.ConstructorStatement(test_case_mock, MagicMock)
    statement_to_ast_visitor.visit_constructor_statement(constr_stmt)
    assert (
        astor.to_source(Module(body=statement_to_ast_visitor.ast_nodes))
        == "var0 = MagicMock()\n"
    )


def test_statement_to_ast_constructor_args(
    statement_to_ast_visitor, test_case_mock, variable_reference_mock,
):
    constr_stmt = param_stmt.ConstructorStatement(
        test_case_mock, MagicMock, [variable_reference_mock]
    )
    statement_to_ast_visitor.visit_constructor_statement(constr_stmt)
    assert (
        astor.to_source(Module(body=statement_to_ast_visitor.ast_nodes))
        == "var0 = MagicMock(var1)\n"
    )


def test_statement_to_ast_constructor_kwargs(
    statement_to_ast_visitor, test_case_mock, variable_reference_mock,
):
    constr_stmt = param_stmt.ConstructorStatement(
        test_case_mock, MagicMock, kwargs={"param1": variable_reference_mock},
    )
    statement_to_ast_visitor.visit_constructor_statement(constr_stmt)
    assert (
        astor.to_source(Module(body=statement_to_ast_visitor.ast_nodes))
        == "var0 = MagicMock(param1=var1)\n"
    )


def test_statement_to_ast_method_no_args(
    statement_to_ast_visitor, test_case_mock, variable_reference_mock
):
    method_stmt = param_stmt.MethodStatement(
        test_case_mock, MagicMock, "test", variable_reference_mock
    )
    statement_to_ast_visitor.visit_method_statement(method_stmt)
    assert (
        astor.to_source(Module(body=statement_to_ast_visitor.ast_nodes))
        == "var0 = var1.test()\n"
    )


def test_statement_to_ast_method_args(
    statement_to_ast_visitor, test_case_mock, variable_reference_mock
):
    method_stmt = param_stmt.MethodStatement(
        test_case_mock,
        MagicMock,
        "test",
        variable_reference_mock,
        [MagicMock(vr.VariableReference)],
    )
    statement_to_ast_visitor.visit_method_statement(method_stmt)
    assert (
        astor.to_source(Module(body=statement_to_ast_visitor.ast_nodes))
        == "var0 = var1.test(var2)\n"
    )


def test_statement_to_ast_method_kwargs(
    statement_to_ast_visitor, test_case_mock, variable_reference_mock
):
    method_stmt = param_stmt.MethodStatement(
        test_case_mock,
        MagicMock,
        "test",
        variable_reference_mock,
        kwargs={"param1": MagicMock(vr.VariableReference)},
    )
    statement_to_ast_visitor.visit_method_statement(method_stmt)
    assert (
        astor.to_source(Module(body=statement_to_ast_visitor.ast_nodes))
        == "var0 = var1.test(param1=var2)\n"
    )
