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
def statement_to_ast_visitor_mock() -> stmt_to_ast.StatementToAstVisitor:
    scope = stmt_to_ast.NamingScope()
    return stmt_to_ast.StatementToAstVisitor(scope)


def test_statement_to_ast_int(statement_to_ast_visitor_mock):
    int_stmt = MagicMock(stmt.Statement)
    int_stmt.value = 5
    statement_to_ast_visitor_mock.visit_int_primitive_statement(int_stmt)
    assert (
        astor.to_source(Module(body=statement_to_ast_visitor_mock.ast_nodes))
        == "var0 = 5\n"
    )


def test_statement_to_ast_float(statement_to_ast_visitor_mock):
    float_stmt = MagicMock(stmt.Statement)
    float_stmt.value = 5.5
    statement_to_ast_visitor_mock.visit_string_primitive_statement(float_stmt)
    assert (
        astor.to_source(Module(body=statement_to_ast_visitor_mock.ast_nodes))
        == "var0 = 5.5\n"
    )


def test_statement_to_ast_str(statement_to_ast_visitor_mock):
    str_stmt = MagicMock(stmt.Statement)
    str_stmt.value = "TestMe"
    statement_to_ast_visitor_mock.visit_string_primitive_statement(str_stmt)
    assert (
        astor.to_source(Module(body=statement_to_ast_visitor_mock.ast_nodes))
        == "var0 = 'TestMe'\n"
    )


def test_statement_to_ast_bool(statement_to_ast_visitor_mock):
    bool_stmt = MagicMock(stmt.Statement)
    bool_stmt.value = True
    statement_to_ast_visitor_mock.visit_string_primitive_statement(bool_stmt)
    assert (
        astor.to_source(Module(body=statement_to_ast_visitor_mock.ast_nodes))
        == "var0 = True\n"
    )
