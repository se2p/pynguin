#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
from typing import Any
from unittest.mock import MagicMock

import pytest

import pynguin.testcase.statement as stmt
import pynguin.testcase.variablereference as vr
import pynguin.utils.generic.genericaccessibleobject as gao

from pynguin.testcase.variablereference import Reference
from pynguin.testcase.variablereference import VariableReference
from pynguin.utils import namingscope as ns


class DummyReference(vr.Reference):
    def get_names(
        self,
        variable_names: ns.AbstractNamingScope,
        module_names: ns.AbstractNamingScope,
    ) -> list[str]:
        pass  # pragma: no cover

    def clone(self, memo: dict[VariableReference, VariableReference]) -> Reference:
        pass  # pragma: no cover

    def structural_eq(self, other: Any, memo: dict[VariableReference, VariableReference]) -> bool:
        pass  # pragma: no cover

    def structural_hash(self, memo: dict[VariableReference, int]) -> int:
        pass  # pragma: no cover

    def get_variable_reference(self) -> VariableReference | None:
        pass  # pragma: no cover

    def replace_variable_reference(self, old: VariableReference, new: VariableReference) -> None:
        pass  # pragma: no cover


@pytest.fixture
def dummy_reference():
    return DummyReference(int)


def test_type(dummy_reference):
    assert dummy_reference.type is int


@pytest.mark.parametrize(
    "type_,result",
    [(int, True), (MagicMock, False)],
)
def test_is_primitive(dummy_reference, type_, result, type_system):
    dummy_reference._type = type_system.convert_type_hint(type_)
    assert dummy_reference.is_primitive() == result


@pytest.mark.parametrize(
    "type_,result",
    [pytest.param(type(None), True), pytest.param(MagicMock, False)],
)
def test_is_none_type(dummy_reference, type_, result, type_system):
    ref = dummy_reference
    ref._type = type_system.convert_type_hint(type_)
    assert ref.is_none_type() == result


def test_var_test_case(test_case_mock):
    ref = vr.VariableReference(test_case_mock, int)
    assert ref.test_case == test_case_mock


def test_var_clone(test_case_mock):
    orig_ref = vr.VariableReference(test_case_mock, int)
    new_ref = vr.VariableReference(test_case_mock, int)

    clone = orig_ref.clone({orig_ref: new_ref})
    assert clone == new_ref


def test_var_get_position(test_case_mock):
    ref = vr.VariableReference(test_case_mock, int)
    ref._test_case = test_case_mock
    statement = MagicMock(stmt.Statement)
    statement.ret_val = ref
    test_case_mock.statements = [statement]
    assert ref.get_statement_position() == 0


def test_var_get_position_no_statements(test_case_mock):
    ref = vr.VariableReference(test_case_mock, int)
    test_case_mock.statements = []
    with pytest.raises(Exception):  # noqa: B017, PT011
        ref.get_statement_position()


def test_var_hash(test_case_mock):
    ref = vr.VariableReference(test_case_mock, int)
    assert ref.structural_hash({ref: 0}) == 0


def test_var_eq_same(test_case_mock):
    ref = vr.VariableReference(test_case_mock, int)
    assert ref.structural_eq(ref, {ref: ref})


def test_var_eq_other_type(test_case_mock):
    ref = vr.VariableReference(test_case_mock, int)
    assert not ref.structural_eq(test_case_mock, {})


def test_var_distance(test_case_mock):
    ref = vr.VariableReference(test_case_mock, int)
    assert ref.distance == 0
    ref.distance = 42
    assert ref.distance == 42


@pytest.fixture
def field_mock():
    return gao.GenericField(MagicMock, "foo", int)


def test_field_source(variable_reference_mock, field_mock):
    ref = vr.FieldReference(variable_reference_mock, field_mock)
    assert ref.source == variable_reference_mock


def test_field_field(variable_reference_mock, field_mock):
    ref = vr.FieldReference(variable_reference_mock, field_mock)
    assert ref.field == field_mock


def test_field_get_names(field_mock):
    ref = vr.FieldReference(vr.VariableReference(MagicMock(), int), field_mock)
    assert ref.get_names(ns.NamingScope(), ns.NamingScope()) == ["var_0", "foo"]


def test_field_clone(field_mock):
    var = vr.VariableReference(MagicMock(), int)
    ref = vr.FieldReference(var, field_mock)
    cloned = ref.clone({var: var})
    assert cloned.field == field_mock
    assert cloned.source == var


def test_field_structural_eq(field_mock):
    var = vr.VariableReference(MagicMock(), int)
    var_2 = vr.VariableReference(MagicMock(), int)
    ref = vr.FieldReference(var, field_mock)
    ref_2 = vr.FieldReference(var_2, field_mock)
    assert ref.structural_eq(ref_2, {var: var_2})


def test_field_structural_eq_2(field_mock):
    var = vr.VariableReference(MagicMock(), int)
    var_2 = vr.VariableReference(MagicMock(), int)
    ref = vr.FieldReference(var, field_mock)
    ref_2 = vr.FieldReference(var, field_mock)
    assert not ref.structural_eq(ref_2, {var: var_2})


def test_field_eq(field_mock):
    var = vr.VariableReference(MagicMock(), int)
    ref = vr.FieldReference(var, field_mock)
    ref_2 = vr.FieldReference(var, field_mock)
    assert ref == ref_2


def test_field_eq_2(field_mock):
    var = vr.VariableReference(MagicMock(), int)
    var_2 = vr.VariableReference(MagicMock(), int)
    ref = vr.FieldReference(var, field_mock)
    ref_2 = vr.FieldReference(var_2, field_mock)
    assert ref != ref_2


def test_field_structural_hash(field_mock):
    var = vr.VariableReference(MagicMock(), int)
    var_2 = vr.VariableReference(MagicMock(), int)
    ref = vr.FieldReference(var, field_mock)
    ref_2 = vr.FieldReference(var_2, field_mock)
    assert ref.structural_hash({var: 0}) == ref_2.structural_hash({var_2: 0})


def test_field_structural_hash_3(field_mock):
    var = vr.VariableReference(MagicMock(), int)
    ref = vr.FieldReference(var, field_mock)
    ref_2 = vr.FieldReference(var, field_mock)
    assert hash(ref) == hash(ref_2)


def test_field_get_var(field_mock):
    var = vr.VariableReference(MagicMock(), int)
    ref = vr.FieldReference(var, field_mock)
    assert ref.get_variable_reference() == var


def test_field_replace_var(field_mock):
    var = vr.VariableReference(MagicMock(), int)
    var_2 = vr.VariableReference(MagicMock(), int)
    ref = vr.FieldReference(var, field_mock)
    ref.replace_variable_reference(var, var_2)
    assert ref.source == var_2


@pytest.fixture
def static_field_mock(type_system):
    return gao.GenericStaticField(
        type_system.to_type_info(MagicMock), "foo", type_system.convert_type_hint(int)
    )


def test_static_field_field(static_field_mock):
    ref = vr.StaticFieldReference(static_field_mock)
    assert ref.field == static_field_mock


def test_static_field_get_names(static_field_mock):
    ref = vr.StaticFieldReference(static_field_mock)
    assert ref.get_names(ns.NamingScope(), ns.NamingScope("module")) == [
        "module_0",
        "MagicMock",
        "foo",
    ]


def test_static_field_clone(static_field_mock):
    ref = vr.StaticFieldReference(static_field_mock)
    cloned = ref.clone({})
    assert cloned.field == static_field_mock


def test_static_field_eq(static_field_mock):
    ref = vr.StaticFieldReference(static_field_mock)
    ref_2 = vr.StaticFieldReference(static_field_mock)
    assert ref == ref_2


def test_static_field_eq_2(static_field_mock):
    ref = vr.StaticFieldReference(static_field_mock)
    ref_2 = vr.StaticFieldReference(gao.GenericStaticField(MagicMock, "bar", int))
    assert ref != ref_2


def test_static_field_hash(static_field_mock):
    ref = vr.StaticFieldReference(static_field_mock)
    ref_2 = vr.StaticFieldReference(static_field_mock)
    assert hash(ref) == hash(ref_2)


def test_static_field_var(static_field_mock):
    ref = vr.StaticFieldReference(static_field_mock)
    assert ref.get_variable_reference() is None


def test_static_field_replace_var(static_field_mock):
    ref = vr.StaticFieldReference(static_field_mock)
    ref.replace_variable_reference(MagicMock(), MagicMock())
    assert ref.get_variable_reference() is None


@pytest.fixture
def static_module_field_mock():
    return gao.GenericStaticModuleField("foomod", "foo", int)


def test_module_field_field(static_module_field_mock):
    ref = vr.StaticModuleFieldReference(static_module_field_mock)
    assert ref.field == static_module_field_mock


def test_module_field_get_names(static_module_field_mock):
    ref = vr.StaticModuleFieldReference(static_module_field_mock)
    assert ref.get_names(ns.NamingScope(), ns.NamingScope("module")) == [
        "module_0",
        "foo",
    ]


def test_module_field_clone(static_module_field_mock):
    ref = vr.StaticModuleFieldReference(static_module_field_mock)
    cloned = ref.clone({})
    assert cloned.field == static_module_field_mock


def test_module_field_eq(static_module_field_mock):
    ref = vr.StaticModuleFieldReference(static_module_field_mock)
    ref_2 = vr.StaticModuleFieldReference(static_module_field_mock)
    assert ref == ref_2


def test_module_field_eq_2(static_module_field_mock):
    ref = vr.StaticModuleFieldReference(static_module_field_mock)
    ref_2 = vr.StaticModuleFieldReference(gao.GenericStaticModuleField("moo", "bar", int))
    assert ref != ref_2


def test_module_field_hash(static_module_field_mock):
    ref = vr.StaticModuleFieldReference(static_module_field_mock)
    ref_2 = vr.StaticModuleFieldReference(static_module_field_mock)
    assert hash(ref) == hash(ref_2)


def test_module_field_var(static_module_field_mock):
    ref = vr.StaticModuleFieldReference(static_module_field_mock)
    assert ref.get_variable_reference() is None


def test_module_field_replace_var(static_module_field_mock):
    ref = vr.StaticModuleFieldReference(static_module_field_mock)
    ref.replace_variable_reference(MagicMock(), MagicMock())
    assert ref.get_variable_reference() is None
