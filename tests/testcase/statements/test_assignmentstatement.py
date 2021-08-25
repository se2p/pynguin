#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
from unittest.mock import MagicMock

import pytest

import pynguin.testcase.statements.assignmentstatement as astmt
import pynguin.testcase.variable.variablereferenceimpl as vri


@pytest.fixture
def assignment_statement(test_case_mock) -> astmt.AssignmentStatement:
    lhs = vri.VariableReferenceImpl(test_case_mock, int)
    rhs = vri.VariableReferenceImpl(test_case_mock, float)
    return astmt.AssignmentStatement(test_case_mock, lhs, rhs)


def test_rhs(test_case_mock, variable_reference_mock):
    rhs = MagicMock(vri.VariableReferenceImpl)
    field_statement = astmt.AssignmentStatement(
        test_case_mock, variable_reference_mock, rhs
    )
    assert field_statement.rhs == rhs


def test_structural_hash(assignment_statement):
    assert assignment_statement.structural_hash() != 0


def test_structural_hash_same(assignment_statement):
    assert (
        assignment_statement.structural_hash() == assignment_statement.structural_hash()
    )


def test_structural_eq_same(assignment_statement):
    assert assignment_statement.structural_eq(
        assignment_statement,
        {
            assignment_statement.ret_val: assignment_statement.ret_val,
            assignment_statement.rhs: assignment_statement.rhs,
        },
    )


def test_structural_eq_other_type(test_case_mock, variable_reference_mock):
    statement = astmt.AssignmentStatement(
        test_case_mock, variable_reference_mock, MagicMock(vri.VariableReferenceImpl)
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
    lhs1 = MagicMock(vri.VariableReferenceImpl)
    lhs1.structural_eq.return_value = lhs
    lhs2 = MagicMock(vri.VariableReferenceImpl)
    rhs1 = MagicMock(vri.VariableReferenceImpl)
    rhs1.structural_eq.return_value = rhs
    rhs2 = MagicMock(vri.VariableReferenceImpl)
    statement_1 = astmt.AssignmentStatement(test_case_mock, lhs1, rhs1)
    statement_2 = astmt.AssignmentStatement(test_case_mock, lhs2, rhs2)
    assert statement_1.structural_eq(statement_2, {lhs1: lhs2, rhs1: rhs2}) == res


def test_accept(test_case_mock, variable_reference_mock):
    statement = astmt.AssignmentStatement(
        test_case_mock, variable_reference_mock, variable_reference_mock
    )
    visitor = MagicMock()
    statement.accept(visitor)
    visitor.visit_assignment_statement.assert_called_with(statement)


def test_accessible_object(assignment_statement):
    assert assignment_statement.accessible_object() is None


def test_mutate(assignment_statement):
    with pytest.raises(Exception):
        assignment_statement.mutate()


def test_get_variable_references(test_case_mock):
    ret_val = MagicMock(vri.VariableReferenceImpl)
    rhs = MagicMock(vri.VariableReferenceImpl)
    statement = astmt.AssignmentStatement(test_case_mock, ret_val, rhs)
    result = statement.get_variable_references()
    assert result == {ret_val, rhs}


def test_replace_ret_val(assignment_statement):
    new = MagicMock(vri.VariableReferenceImpl)
    old = assignment_statement.ret_val
    assignment_statement.replace(old, new)
    assert assignment_statement.ret_val == new


def test_replace_rhs(assignment_statement):
    new = MagicMock(vri.VariableReferenceImpl)
    old = assignment_statement.rhs
    assignment_statement.replace(old, new)
    assert assignment_statement.rhs == new
