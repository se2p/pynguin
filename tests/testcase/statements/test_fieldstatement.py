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
from unittest import mock
from unittest.mock import MagicMock

import pynguin.configuration as config
import pynguin.testcase.defaulttestcase as dtc
import pynguin.testcase.statements.fieldstatement as fstmt
import pynguin.testcase.statements.parametrizedstatements as ps
import pynguin.testcase.statements.primitivestatements as prim
import pynguin.testcase.statements.statementvisitor as sv
import pynguin.testcase.variable.variablereference as vr
import pynguin.testcase.variable.variablereferenceimpl as vri


def test_field_statement(test_case_mock, variable_reference_mock, field_mock):
    field_statement = fstmt.FieldStatement(
        test_case_mock, field_mock, variable_reference_mock
    )
    assert field_statement.field == field_mock


def test_new_source(test_case_mock, variable_reference_mock, field_mock):
    stmt = fstmt.FieldStatement(test_case_mock, field_mock, variable_reference_mock)
    new_source = MagicMock(vr.VariableReference)
    stmt.source = new_source
    assert stmt.source == new_source


def test_accessible_object(test_case_mock, variable_reference_mock, field_mock):
    stmt = fstmt.FieldStatement(test_case_mock, field_mock, variable_reference_mock)
    assert stmt.accessible_object() == field_mock


def test_field_statement_eq_same(test_case_mock, variable_reference_mock, field_mock):
    statement = fstmt.FieldStatement(
        test_case_mock, field_mock, variable_reference_mock
    )
    assert statement.__eq__(statement)


def test_constructor_statement_accept(
    test_case_mock, variable_reference_mock, field_mock
):
    statement = fstmt.FieldStatement(
        test_case_mock, field_mock, variable_reference_mock
    )
    visitor = MagicMock(sv.StatementVisitor)
    statement.accept(visitor)

    visitor.visit_field_statement.assert_called_once_with(statement)


def test_get_var_references(test_case_mock, variable_reference_mock, field_mock):
    statement = fstmt.FieldStatement(
        test_case_mock, field_mock, variable_reference_mock
    )
    assert statement.get_variable_references() == {variable_reference_mock}


def test_primitive_statement_replace(field_mock):
    test_case = dtc.DefaultTestCase()
    ref = prim.IntPrimitiveStatement(test_case, 5)
    test_case.add_statement(ref)
    statement = fstmt.FieldStatement(test_case, field_mock, ref.return_value)
    test_case.add_statement(statement)
    new = vri.VariableReferenceImpl(test_case, int)

    statement.replace(ref.return_value, new)
    assert statement.source == new


def test_primitive_statement_replace_ignore(field_mock):
    test_case = dtc.DefaultTestCase()
    ref = prim.IntPrimitiveStatement(test_case, 5)
    statement = fstmt.FieldStatement(test_case, field_mock, ref.return_value)
    new = prim.FloatPrimitiveStatement(test_case, 0).return_value
    old = statement.source
    statement.replace(new, new)
    assert statement.source == old


def test_field_statement_eq_other_type(
    test_case_mock, variable_reference_mock, field_mock
):
    statement = fstmt.FieldStatement(
        test_case_mock, field_mock, variable_reference_mock
    )
    assert not statement.__eq__(variable_reference_mock)


def test_field_statement_eq_clone(field_mock):
    test_case1 = dtc.DefaultTestCase()
    test_case1.add_statement(prim.IntPrimitiveStatement(test_case1, 0))
    test_case2 = dtc.DefaultTestCase()
    test_case2.add_statement(prim.IntPrimitiveStatement(test_case2, 0))

    statement = fstmt.FieldStatement(
        test_case1, field_mock, test_case1.statements[0].return_value
    )
    test_case1.add_statement(statement)
    clone = statement.clone(test_case2)
    test_case2.add_statement(clone)
    assert statement.__eq__(clone)


def test_hash_same(test_case_mock, variable_reference_mock, field_mock):
    statement = fstmt.FieldStatement(
        test_case_mock, field_mock, variable_reference_mock
    )
    statement2 = fstmt.FieldStatement(
        test_case_mock, field_mock, variable_reference_mock
    )
    assert hash(statement) == hash(statement2)


def test_mutate_not(test_case_mock, field_mock, variable_reference_mock):
    config.INSTANCE.change_parameter_probability = 0.0
    statement = fstmt.FieldStatement(
        test_case_mock, field_mock, variable_reference_mock
    )
    assert not statement.mutate()


def test_mutate_no_replacements(field_mock, constructor_mock):
    config.INSTANCE.change_parameter_probability = 1.0
    test_case = dtc.DefaultTestCase()
    const = ps.ConstructorStatement(test_case, constructor_mock)
    field = fstmt.FieldStatement(test_case, field_mock, const.return_value)
    test_case.add_statement(const)
    test_case.add_statement(field)
    assert not field.mutate()


def test_mutate_success(field_mock, constructor_mock):
    config.INSTANCE.change_parameter_probability = 1.0
    test_case = dtc.DefaultTestCase()
    const = ps.ConstructorStatement(test_case, constructor_mock)
    const2 = ps.ConstructorStatement(test_case, constructor_mock)
    field = fstmt.FieldStatement(test_case, field_mock, const.return_value)
    const3 = ps.ConstructorStatement(test_case, constructor_mock)
    test_case.add_statement(const)
    test_case.add_statement(const2)
    test_case.add_statement(field)
    test_case.add_statement(const3)
    assert field.mutate()
    assert field.source == const2.return_value
