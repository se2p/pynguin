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
import pynguin.testcase.statements.fieldstatement as field_stmt

import astor
import pytest

import pynguin.testcase.statement_to_ast as stmt_to_ast
import pynguin.testcase.variable.variablereference as vr
import pynguin.testcase.statements.statement as stmt


def test_naming_scope_same(variable_reference_mock):
    scope = stmt_to_ast.NamingScope()
    name1 = scope.get_name(variable_reference_mock)
    name2 = scope.get_name(variable_reference_mock)
    assert name1 == name2


def test_naming_scope_different(variable_reference_mock):
    scope = stmt_to_ast.NamingScope()
    name1 = scope.get_name(variable_reference_mock)
    name2 = scope.get_name(MagicMock(vr.VariableReference))
    assert name1 != name2


def test_naming_scope_known_indices_empty():
    scope = stmt_to_ast.NamingScope()
    assert scope.known_name_indices == {}


def test_naming_scope_known_indices_not_empty(variable_reference_mock):
    scope = stmt_to_ast.NamingScope()
    scope.get_name(variable_reference_mock)
    assert scope.known_name_indices == {variable_reference_mock: 0}


@pytest.fixture()
def statement_to_ast_visitor() -> stmt_to_ast.StatementToAstVisitor:
    var_names = stmt_to_ast.NamingScope()
    module_aliases = stmt_to_ast.NamingScope(prefix="module")
    return stmt_to_ast.StatementToAstVisitor(module_aliases, var_names)


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
    statement_to_ast_visitor.visit_float_primitive_statement(float_stmt)
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
    statement_to_ast_visitor.visit_boolean_primitive_statement(bool_stmt)
    assert (
        astor.to_source(Module(body=statement_to_ast_visitor.ast_nodes))
        == "var0 = True\n"
    )


def test_statement_to_ast_none(statement_to_ast_visitor):
    none_stmt = MagicMock(stmt.Statement)
    none_stmt.value = None
    statement_to_ast_visitor.visit_none_statement(none_stmt)
    assert (
        astor.to_source(Module(body=statement_to_ast_visitor.ast_nodes))
        == "var0 = None\n"
    )


def test_statement_to_ast_assignment(variable_reference_mock, statement_to_ast_visitor):
    assign_stmt = MagicMock(stmt.Statement)
    assign_stmt.return_value = variable_reference_mock
    assign_stmt.rhs = variable_reference_mock
    statement_to_ast_visitor.visit_assignment_statement(assign_stmt)
    assert (
        astor.to_source(Module(body=statement_to_ast_visitor.ast_nodes))
        == "var0 = var0\n"
    )


def test_statement_to_ast_field(
    statement_to_ast_visitor, test_case_mock, field_mock, variable_reference_mock
):
    f_stmt = field_stmt.FieldStatement(
        test_case_mock, field_mock, variable_reference_mock
    )
    statement_to_ast_visitor.visit_field_statement(f_stmt)


def test_statement_to_ast_constructor_no_args(
    statement_to_ast_visitor, test_case_mock, constructor_mock
):
    constr_stmt = param_stmt.ConstructorStatement(test_case_mock, constructor_mock)
    statement_to_ast_visitor.visit_constructor_statement(constr_stmt)
    assert (
        astor.to_source(Module(body=statement_to_ast_visitor.ast_nodes))
        == "var0 = module0.SomeType()\n"
    )


def test_statement_to_ast_constructor_args(
    statement_to_ast_visitor, test_case_mock, variable_reference_mock, constructor_mock
):
    constr_stmt = param_stmt.ConstructorStatement(
        test_case_mock, constructor_mock, [variable_reference_mock]
    )
    statement_to_ast_visitor.visit_constructor_statement(constr_stmt)
    assert (
        astor.to_source(Module(body=statement_to_ast_visitor.ast_nodes))
        == "var0 = module0.SomeType(var1)\n"
    )


def test_statement_to_ast_constructor_kwargs(
    statement_to_ast_visitor, test_case_mock, variable_reference_mock, constructor_mock
):
    constr_stmt = param_stmt.ConstructorStatement(
        test_case_mock, constructor_mock, kwargs={"param1": variable_reference_mock},
    )
    statement_to_ast_visitor.visit_constructor_statement(constr_stmt)
    assert (
        astor.to_source(Module(body=statement_to_ast_visitor.ast_nodes))
        == "var0 = module0.SomeType(param1=var1)\n"
    )


def test_statement_to_ast_method_no_args(
    statement_to_ast_visitor, test_case_mock, variable_reference_mock, method_mock
):
    method_stmt = param_stmt.MethodStatement(
        test_case_mock, method_mock, variable_reference_mock
    )
    statement_to_ast_visitor.visit_method_statement(method_stmt)
    assert (
        astor.to_source(Module(body=statement_to_ast_visitor.ast_nodes))
        == "var0 = var1.simple_method()\n"
    )


def test_statement_to_ast_method_args(
    statement_to_ast_visitor, test_case_mock, variable_reference_mock, method_mock
):
    method_stmt = param_stmt.MethodStatement(
        test_case_mock,
        method_mock,
        variable_reference_mock,
        [MagicMock(vr.VariableReference)],
    )
    statement_to_ast_visitor.visit_method_statement(method_stmt)
    assert (
        astor.to_source(Module(body=statement_to_ast_visitor.ast_nodes))
        == "var0 = var1.simple_method(var2)\n"
    )


def test_statement_to_ast_method_kwargs(
    statement_to_ast_visitor, test_case_mock, variable_reference_mock, method_mock
):
    method_stmt = param_stmt.MethodStatement(
        test_case_mock,
        method_mock,
        variable_reference_mock,
        kwargs={"param1": MagicMock(vr.VariableReference)},
    )
    statement_to_ast_visitor.visit_method_statement(method_stmt)
    assert (
        astor.to_source(Module(body=statement_to_ast_visitor.ast_nodes))
        == "var0 = var1.simple_method(param1=var2)\n"
    )


def test_statement_to_ast_function_no_args(
    statement_to_ast_visitor, test_case_mock, function_mock
):
    function_stmt = param_stmt.FunctionStatement(test_case_mock, function_mock)
    statement_to_ast_visitor.visit_function_statement(function_stmt)
    assert (
        astor.to_source(Module(body=statement_to_ast_visitor.ast_nodes))
        == "var0 = module0.simple_function()\n"
    )


def test_statement_to_ast_function_args(
    statement_to_ast_visitor, test_case_mock, function_mock
):
    function_stmt = param_stmt.FunctionStatement(
        test_case_mock, function_mock, [MagicMock(vr.VariableReference)]
    )
    statement_to_ast_visitor.visit_function_statement(function_stmt)
    assert (
        astor.to_source(Module(body=statement_to_ast_visitor.ast_nodes))
        == "var0 = module0.simple_function(var1)\n"
    )


def test_statement_to_ast_function_kwargs(
    statement_to_ast_visitor, test_case_mock, function_mock
):
    function_stmt = param_stmt.FunctionStatement(
        test_case_mock,
        function_mock,
        kwargs={"param1": MagicMock(vr.VariableReference)},
    )
    statement_to_ast_visitor.visit_function_statement(function_stmt)
    assert (
        astor.to_source(Module(body=statement_to_ast_visitor.ast_nodes))
        == "var0 = module0.simple_function(param1=var1)\n"
    )
