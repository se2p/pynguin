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
from unittest.mock import MagicMock

import pynguin.testcase.statements.parametrizedstatements as ps
import pynguin.testcase.variable.variablereferenceimpl as vri
import pynguin.testcase.statements.statementvisitor as sv


def test_constructor_statement_no_args(test_case_mock, variable_reference_mock):
    statement = ps.ConstructorStatement(test_case_mock, str)
    assert statement.args == []
    assert statement.kwargs == {}


def test_constructor_statement_args(test_case_mock, variable_reference_mock):
    statement = ps.ConstructorStatement(test_case_mock, str)
    references = [
        MagicMock(vri.VariableReferenceImpl),
        MagicMock(vri.VariableReferenceImpl),
    ]
    statement.args = references
    assert statement.args == references


def test_constructor_statement_kwargs(test_case_mock, variable_reference_mock):
    statement = ps.ConstructorStatement(test_case_mock, str)
    references = {
        "par1": MagicMock(vri.VariableReferenceImpl),
        "par2": MagicMock(vri.VariableReferenceImpl),
    }
    statement.kwargs = references
    assert statement.kwargs == references


def test_constructor_statement_accept(test_case_mock, variable_reference_mock):
    statement = ps.ConstructorStatement(test_case_mock, str)
    visitor = MagicMock(sv.StatementVisitor)
    statement.accept(visitor)

    visitor.visit_constructor_statement.assert_called_once_with(statement)


def test_constructor_statement_hash(test_case_mock, variable_reference_mock):
    statement = ps.ConstructorStatement(test_case_mock, str)
    assert statement.__hash__() != 0


def test_constructor_statement_eq_same(test_case_mock, variable_reference_mock):
    statement = ps.ConstructorStatement(test_case_mock, str)
    assert statement.__eq__(statement)


def test_constructor_statement_eq_other_type(test_case_mock, variable_reference_mock):
    statement = ps.ConstructorStatement(test_case_mock, str)
    assert not statement.__eq__(variable_reference_mock)


def test_method_statement_no_args(test_case_mock, variable_reference_mock):
    statement = ps.MethodStatement(test_case_mock, "", variable_reference_mock, str)
    assert statement.args == []
    assert statement.kwargs == {}


def test_method_statement_args(test_case_mock, variable_reference_mock):
    references = [
        MagicMock(vri.VariableReferenceImpl),
        MagicMock(vri.VariableReferenceImpl),
    ]

    statement = ps.MethodStatement(test_case_mock, "", variable_reference_mock, str)
    statement.args = references
    assert statement.args == references


def test_method_statement_kwargs(test_case_mock, variable_reference_mock):
    references = {
        "par1": MagicMock(vri.VariableReferenceImpl),
        "par2": MagicMock(vri.VariableReferenceImpl),
    }

    statement = ps.MethodStatement(test_case_mock, "", variable_reference_mock, str)
    statement.kwargs = references
    assert statement.kwargs == references


def test_method_statement_accept(test_case_mock, variable_reference_mock):
    statement = ps.MethodStatement(test_case_mock, "", variable_reference_mock, str)
    visitor = MagicMock(sv.StatementVisitor)
    statement.accept(visitor)

    visitor.visit_method_statement.assert_called_once_with(statement)
