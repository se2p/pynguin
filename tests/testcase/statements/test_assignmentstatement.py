#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
from unittest.mock import MagicMock

import pytest

import pynguin.testcase.variablereference as vr
import pynguin.utils.generic.genericaccessibleobject as gao

from pynguin.testcase.statement import AssignmentStatement


@pytest.fixture
def assignment_statement(test_case_mock) -> AssignmentStatement:
    lhs = vr.FieldReference(
        vr.VariableReference(test_case_mock, int),
        gao.GenericField(MagicMock, "foo", int),
    )
    rhs = vr.VariableReference(test_case_mock, float)
    return AssignmentStatement(test_case_mock, lhs, rhs)


def test_rhs(test_case_mock, variable_reference_mock):
    rhs = MagicMock(vr.VariableReference)
    field_statement = AssignmentStatement(test_case_mock, variable_reference_mock, rhs)
    assert field_statement.rhs == rhs


def test_structural_hash(assignment_statement):
    assert (
        assignment_statement.structural_hash({
            assignment_statement.lhs.source: 0,
            assignment_statement.rhs: 1,
        })
        != 0
    )


def test_structural_hash_same(assignment_statement):
    memo = {assignment_statement.lhs.source: 0, assignment_statement.rhs: 1}
    assert assignment_statement.structural_hash(memo) == assignment_statement.structural_hash(memo)


def test_structural_eq_same(assignment_statement):
    # fmt: off
    assert assignment_statement.structural_eq(
        assignment_statement,
        {
            assignment_statement.lhs.get_variable_reference(): assignment_statement.lhs
            .get_variable_reference(),
            assignment_statement.rhs: assignment_statement.rhs,
        },
    )
    # fmt: on


def test_structural_eq_other_type(test_case_mock, variable_reference_mock):
    statement = AssignmentStatement(
        test_case_mock, variable_reference_mock, MagicMock(vr.VariableReference)
    )
    assert not statement.structural_eq(test_case_mock, {})


@pytest.mark.parametrize(
    "lhs,rhs,res",
    [
        (True, True, True),
        (True, False, False),
        (False, True, False),
        (False, False, False),
    ],
)
def test_structural_eq_other_different_types(test_case_mock, lhs, rhs, res):
    lhs1 = MagicMock(vr.VariableReference)
    lhs1.structural_eq.return_value = lhs
    lhs2 = MagicMock(vr.VariableReference)
    rhs1 = MagicMock(vr.VariableReference)
    rhs1.structural_eq.return_value = rhs
    rhs2 = MagicMock(vr.VariableReference)
    statement_1 = AssignmentStatement(test_case_mock, lhs1, rhs1)
    statement_2 = AssignmentStatement(test_case_mock, lhs2, rhs2)
    assert statement_1.structural_eq(statement_2, {lhs1: lhs2, rhs1: rhs2}) == res


def test_accept(test_case_mock, variable_reference_mock):
    statement = AssignmentStatement(
        test_case_mock, variable_reference_mock, variable_reference_mock
    )
    visitor = MagicMock()
    statement.accept(visitor)
    visitor.visit_assignment_statement.assert_called_with(statement)


def test_accessible_object(assignment_statement):
    assert assignment_statement.accessible_object() is None


def test_mutate(assignment_statement):
    with pytest.raises(Exception):  # noqa: B017, PT011
        assignment_statement.mutate()


def test_get_variable_references(assignment_statement):
    result = assignment_statement.get_variable_references()
    assert result == {
        assignment_statement.lhs.get_variable_reference(),
        assignment_statement.rhs,
    }


def test_replace_ret_val(test_case_mock, assignment_statement):
    new = vr.VariableReference(test_case_mock, int)
    old = assignment_statement.lhs.get_variable_reference()
    assignment_statement.replace(old, new)
    assert assignment_statement.lhs.get_variable_reference() == new


def test_replace_rhs(test_case_mock, assignment_statement):
    new = vr.VariableReference(test_case_mock, int)
    old = assignment_statement.rhs
    assignment_statement.replace(old, new)
    assert assignment_statement.rhs == new
