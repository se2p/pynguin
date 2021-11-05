#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
from unittest.mock import MagicMock

import pytest

import pynguin.testcase.statement as stmt
import pynguin.testcase.variablereference as vr


def test_getters(test_case_mock):
    ref = vr.VariableReferenceImpl(test_case_mock, int)
    assert ref.variable_type == int
    assert ref.test_case == test_case_mock


def test_setters(test_case_mock):
    ref = vr.VariableReferenceImpl(test_case_mock, int)
    vt_new = float
    ref.variable_type = vt_new
    assert ref.variable_type == vt_new


def test_clone(test_case_mock):
    orig_ref = vr.VariableReferenceImpl(test_case_mock, int)
    new_ref = vr.VariableReferenceImpl(test_case_mock, int)

    clone = orig_ref.clone({orig_ref: new_ref})
    assert clone == new_ref


def test_get_position(test_case_mock):
    ref = vr.VariableReferenceImpl(test_case_mock, int)
    ref._test_case = test_case_mock
    statement = MagicMock(stmt.Statement)
    statement.ret_val = ref
    test_case_mock.statements = [statement]
    assert ref.get_statement_position() == 0


def test_get_position_no_statements(test_case_mock):
    ref = vr.VariableReferenceImpl(test_case_mock, int)
    test_case_mock.statements = []
    with pytest.raises(Exception):
        ref.get_statement_position()


def test_hash(test_case_mock):
    ref = vr.VariableReferenceImpl(test_case_mock, int)
    assert ref.structural_hash() != 0


def test_eq_same(test_case_mock):
    ref = vr.VariableReferenceImpl(test_case_mock, int)
    assert ref.structural_eq(ref, {ref: ref})


def test_eq_differnt_var_type(test_case_mock):
    ref1 = vr.VariableReferenceImpl(test_case_mock, int)
    ref2 = vr.VariableReferenceImpl(test_case_mock, float)
    assert not ref1.structural_eq(ref2, {ref1: ref2})


def test_eq_other_type(test_case_mock):
    ref = vr.VariableReferenceImpl(test_case_mock, int)
    assert not ref.structural_eq(test_case_mock, {})


def test_distance(test_case_mock):
    ref = vr.VariableReferenceImpl(test_case_mock, int)
    assert ref.distance == 0
    ref.distance = 42
    assert ref.distance == 42


@pytest.mark.parametrize(
    "type_,result",
    [pytest.param(int, True), pytest.param(MagicMock, False)],
)
def test_is_primitive(test_case_mock, type_, result):
    ref = vr.VariableReferenceImpl(test_case_mock, type_)
    assert ref.is_primitive() == result


@pytest.mark.parametrize(
    "type_,result",
    [pytest.param(None, True), pytest.param(MagicMock, False)],
)
def test_is_type_unknown(test_case_mock, type_, result):
    ref = vr.VariableReferenceImpl(test_case_mock, type_)
    assert ref.is_type_unknown() == result


@pytest.mark.parametrize(
    "type_,result",
    [pytest.param(type(None), True), pytest.param(MagicMock, False)],
)
def test_is_none_type(test_case_mock, type_, result):
    ref = vr.VariableReferenceImpl(test_case_mock, type_)
    assert ref.is_none_type() == result
