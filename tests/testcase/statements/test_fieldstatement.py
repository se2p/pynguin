#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
from unittest.mock import MagicMock

import pynguin.configuration as config
import pynguin.testcase.defaulttestcase as dtc
import pynguin.testcase.statements.fieldstatement as fstmt
import pynguin.testcase.statements.parametrizedstatements as ps
import pynguin.testcase.statements.primitivestatements as prim
import pynguin.testcase.statements.statementvisitor as sv
import pynguin.testcase.variablereference as vr


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
    statement = fstmt.FieldStatement(test_case, field_mock, ref.ret_val)
    test_case.add_statement(statement)
    new = vr.VariableReferenceImpl(test_case, int)

    statement.replace(ref.ret_val, new)
    assert statement.source == new


def test_primitive_statement_replace_ignore(field_mock):
    test_case = dtc.DefaultTestCase()
    ref = prim.IntPrimitiveStatement(test_case, 5)
    statement = fstmt.FieldStatement(test_case, field_mock, ref.ret_val)
    new = prim.FloatPrimitiveStatement(test_case, 0).ret_val
    old = statement.source
    statement.replace(new, new)
    assert statement.source == old


def test_field_statement_eq_other_type(
    test_case_mock, variable_reference_mock, field_mock
):
    statement = fstmt.FieldStatement(
        test_case_mock, field_mock, variable_reference_mock
    )
    assert not statement.structural_eq(variable_reference_mock, {})


def test_field_statement_eq_clone(test_case_mock, field_mock):
    ref = vr.VariableReferenceImpl(test_case_mock, float)
    statement = fstmt.FieldStatement(test_case_mock, field_mock, ref)
    memo = {ref: ref}
    clone = statement.clone(test_case_mock, memo)
    memo[statement.ret_val] = clone.ret_val
    assert statement.structural_eq(clone, memo)


def test_hash_same(test_case_mock, variable_reference_mock, field_mock):
    statement = fstmt.FieldStatement(
        test_case_mock, field_mock, variable_reference_mock
    )
    statement2 = fstmt.FieldStatement(
        test_case_mock, field_mock, variable_reference_mock
    )
    assert statement.structural_hash() == statement2.structural_hash()


def test_mutate_not(test_case_mock, field_mock, variable_reference_mock):
    config.configuration.search_algorithm.change_parameter_probability = 0.0
    statement = fstmt.FieldStatement(
        test_case_mock, field_mock, variable_reference_mock
    )
    assert not statement.mutate()


def test_mutate_no_replacements(field_mock, constructor_mock):
    config.configuration.search_algorithm.change_parameter_probability = 1.0
    test_case = dtc.DefaultTestCase()
    const = ps.ConstructorStatement(test_case, constructor_mock)
    field = fstmt.FieldStatement(test_case, field_mock, const.ret_val)
    test_case.add_statement(const)
    test_case.add_statement(field)
    assert not field.mutate()


def test_mutate_success(field_mock, constructor_mock):
    config.configuration.search_algorithm.change_parameter_probability = 1.0
    test_case = dtc.DefaultTestCase()
    const = ps.ConstructorStatement(test_case, constructor_mock)
    const2 = ps.ConstructorStatement(test_case, constructor_mock)
    field = fstmt.FieldStatement(test_case, field_mock, const.ret_val)
    const3 = ps.ConstructorStatement(test_case, constructor_mock)
    test_case.add_statement(const)
    test_case.add_statement(const2)
    test_case.add_statement(field)
    test_case.add_statement(const3)
    assert field.mutate()
    assert field.source == const2.ret_val
