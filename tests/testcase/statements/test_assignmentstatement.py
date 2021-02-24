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
def assignment_statement(test_case_mock, variable_reference_mock):
    return astmt.AssignmentStatement(
        test_case_mock, variable_reference_mock, MagicMock(vri.VariableReferenceImpl)
    )


def test_field_statement(test_case_mock, variable_reference_mock):
    rhs = MagicMock(vri.VariableReferenceImpl)
    field_statement = astmt.AssignmentStatement(
        test_case_mock, variable_reference_mock, rhs
    )
    assert field_statement.rhs == rhs


def test_hash(assignment_statement):
    assert assignment_statement.__hash__() != 0


def test_eq_same(assignment_statement):
    assert assignment_statement.__eq__(assignment_statement)


def test_eq_other_type(test_case_mock, variable_reference_mock):
    statement = astmt.AssignmentStatement(
        test_case_mock, variable_reference_mock, MagicMock(vri.VariableReferenceImpl)
    )
    assert not statement.__eq__(test_case_mock)


def test_eq_other(test_case_mock, variable_reference_mock):
    statement_1 = astmt.AssignmentStatement(
        test_case_mock, variable_reference_mock, variable_reference_mock
    )
    statement_2 = astmt.AssignmentStatement(
        test_case_mock, variable_reference_mock, variable_reference_mock
    )
    assert statement_1.__eq__(statement_2)


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
