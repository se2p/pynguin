#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
from unittest.mock import MagicMock

import pynguin.configuration as config
import pynguin.testcase.statement as stmt
import pynguin.testcase.variablereference as vr
import pynguin.utils.generic.genericaccessibleobject as gao

from tests.testutils import feed_typesystem


def test_field_statement(test_case_mock, variable_reference_mock, field_mock):
    field_statement = stmt.FieldStatement(test_case_mock, field_mock, variable_reference_mock)
    assert field_statement.field == field_mock


def test_new_source(test_case_mock, variable_reference_mock, field_mock):
    statement = stmt.FieldStatement(test_case_mock, field_mock, variable_reference_mock)
    new_source = MagicMock(vr.VariableReference)
    statement.source = new_source
    assert statement.source == new_source


def test_accessible_object(test_case_mock, variable_reference_mock, field_mock):
    statement = stmt.FieldStatement(test_case_mock, field_mock, variable_reference_mock)
    assert statement.accessible_object() == field_mock


def test_field_statement_eq_same(test_case_mock, variable_reference_mock, field_mock):
    statement = stmt.FieldStatement(test_case_mock, field_mock, variable_reference_mock)
    assert statement == statement  # noqa: PLR0124


def test_constructor_statement_accept(test_case_mock, variable_reference_mock, field_mock):
    statement = stmt.FieldStatement(test_case_mock, field_mock, variable_reference_mock)
    visitor = MagicMock(stmt.StatementVisitor)
    statement.accept(visitor)

    visitor.visit_field_statement.assert_called_once_with(statement)


def test_get_var_references(default_test_case, field_mock):
    var = vr.VariableReference(
        default_test_case,
        default_test_case.test_cluster.type_system.convert_type_hint(int),
    )
    statement = stmt.FieldStatement(default_test_case, field_mock, var)
    assert statement.get_variable_references() == {var, statement.ret_val}


def test_statement_replace(field_mock, default_test_case):
    ref = vr.VariableReference(
        default_test_case,
        default_test_case.test_cluster.type_system.convert_type_hint(int),
    )
    statement = stmt.FieldStatement(default_test_case, field_mock, ref)
    new = vr.VariableReference(
        default_test_case,
        default_test_case.test_cluster.type_system.convert_type_hint(int),
    )

    statement.replace(ref, new)
    assert statement.source == new


def test_statement_replace_2(field_mock, default_test_case):
    ref = vr.VariableReference(
        default_test_case,
        default_test_case.test_cluster.type_system.convert_type_hint(int),
    )
    statement = stmt.FieldStatement(default_test_case, field_mock, ref)
    new = vr.VariableReference(
        default_test_case,
        default_test_case.test_cluster.type_system.convert_type_hint(int),
    )

    statement.replace(statement.ret_val, new)
    assert statement.ret_val == new


def test_statement_replace_3(field_mock, default_test_case):
    ref = vr.VariableReference(
        default_test_case,
        default_test_case.test_cluster.type_system.convert_type_hint(int),
    )
    ref_2 = vr.FieldReference(
        ref,
        gao.GenericField(
            default_test_case.test_cluster.type_system.to_type_info(MagicMock),
            "foo",
            default_test_case.test_cluster.type_system.convert_type_hint(int),
        ),
    )
    statement = stmt.FieldStatement(default_test_case, field_mock, ref_2)
    new = vr.VariableReference(
        default_test_case,
        default_test_case.test_cluster.type_system.convert_type_hint(int),
    )

    statement.replace(ref, new)
    assert statement.source.get_variable_reference() == new


def test_primitive_statement_replace_ignore(field_mock, default_test_case):
    ref = stmt.IntPrimitiveStatement(default_test_case, 5)
    statement = stmt.FieldStatement(default_test_case, field_mock, ref.ret_val)
    new = stmt.FloatPrimitiveStatement(default_test_case, 0).ret_val
    old = statement.source
    statement.replace(new, new)
    assert statement.source == old


def test_field_statement_eq_other_type(default_test_case, variable_reference_mock, field_mock):
    statement = stmt.FieldStatement(default_test_case, field_mock, variable_reference_mock)
    assert not statement.structural_eq(variable_reference_mock, {})


def test_field_statement_eq_clone(default_test_case, field_mock):
    ref = vr.VariableReference(
        default_test_case,
        default_test_case.test_cluster.type_system.convert_type_hint(int),
    )
    statement = stmt.FieldStatement(default_test_case, field_mock, ref)
    memo = {ref: ref}
    clone = statement.clone(default_test_case, memo)
    memo[statement.ret_val] = clone.ret_val
    assert statement.structural_eq(clone, memo)


def test_hash_same(default_test_case, variable_reference_mock, field_mock):
    statement = stmt.FieldStatement(default_test_case, field_mock, variable_reference_mock)
    statement2 = stmt.FieldStatement(default_test_case, field_mock, variable_reference_mock)
    memo = {variable_reference_mock: 0, statement.ret_val: 1}
    memo2 = {variable_reference_mock: 0, statement2.ret_val: 1}
    assert statement.structural_hash(memo) == statement2.structural_hash(memo2)


def test_mutate_not(test_case_mock, field_mock, variable_reference_mock):
    config.configuration.search_algorithm.change_parameter_probability = 0.0
    statement = stmt.FieldStatement(test_case_mock, field_mock, variable_reference_mock)
    assert not statement.mutate()


def test_mutate_no_replacements(field_mock, constructor_mock, default_test_case):
    config.configuration.search_algorithm.change_parameter_probability = 1.0
    const = stmt.ConstructorStatement(default_test_case, constructor_mock)
    field = stmt.FieldStatement(default_test_case, field_mock, const.ret_val)
    default_test_case.add_statement(const)
    default_test_case.add_statement(field)
    feed_typesystem(default_test_case.test_cluster.type_system, field_mock)
    assert not field.mutate()


def test_mutate_success(field_mock, constructor_mock, default_test_case):
    config.configuration.search_algorithm.change_parameter_probability = 1.0
    const = stmt.ConstructorStatement(default_test_case, constructor_mock)
    const2 = stmt.ConstructorStatement(default_test_case, constructor_mock)
    field = stmt.FieldStatement(default_test_case, field_mock, const.ret_val)
    const3 = stmt.ConstructorStatement(default_test_case, constructor_mock)
    default_test_case.add_statement(const)
    default_test_case.add_statement(const2)
    default_test_case.add_statement(field)
    default_test_case.add_statement(const3)
    feed_typesystem(default_test_case.test_cluster.type_system, field_mock)
    assert field.mutate()
    assert field.source == const2.ret_val
