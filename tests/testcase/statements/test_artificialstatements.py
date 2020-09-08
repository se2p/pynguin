#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
from unittest.mock import MagicMock

import pytest

import pynguin.testcase.statements.artificialstatements as arts
import pynguin.testcase.statements.statementvisitor as sv
import pynguin.testcase.testcase as tc
import pynguin.testcase.variable.variablereference as vr
import pynguin.testcase.variable.variablereferenceimpl as vri


@pytest.fixture
def duck_mock_statement() -> arts.DuckMockArtificialStatement:
    return arts.DuckMockArtificialStatement(
        MagicMock(tc.TestCase),
        MagicMock(vr.VariableReference),
    )


def test_artificial_statement_mutate(duck_mock_statement):
    assert not duck_mock_statement.mutate()


def test_duck_mock_clone():
    test_case_1 = MagicMock(tc.TestCase)
    test_case_2 = MagicMock(tc.TestCase)
    reference = vri.VariableReferenceImpl(test_case_1, None)
    original = arts.DuckMockArtificialStatement(test_case_1, reference)
    clone = original.clone(test_case_2)
    assert clone.test_case == test_case_2
    assert clone.return_value.test_case == reference.test_case


def test_duck_mock_accept(duck_mock_statement):
    visitor = MagicMock(sv.StatementVisitor)
    duck_mock_statement.accept(visitor)
    visitor.visit_duck_mock_artificial_statement.assert_called_once()


def test_duck_mock_accessible_object(duck_mock_statement):
    assert duck_mock_statement.accessible_object() is None


def test_duck_mock_get_variable_references(duck_mock_statement):
    assert duck_mock_statement.get_variable_references() == {
        duck_mock_statement.return_value
    }


def test_duck_mock_replace_no_replace(duck_mock_statement):
    old_return_value = duck_mock_statement.return_value
    new_return_value = MagicMock(vr.VariableReference)
    duck_mock_statement.replace(new_return_value, new_return_value)
    assert duck_mock_statement.return_value == old_return_value


def test_duck_mock_replace(duck_mock_statement):
    old_return_value = duck_mock_statement.return_value
    new_return_value = MagicMock(vr.VariableReference)
    duck_mock_statement.replace(old_return_value, new_return_value)
    assert duck_mock_statement.return_value == new_return_value


def test_duck_mock_eq_other_type(duck_mock_statement):
    assert not duck_mock_statement.__eq__(MagicMock(str))


def test_duck_mock_eq_same(duck_mock_statement):
    assert duck_mock_statement.__eq__(duck_mock_statement)


def test_duck_mock_eq_same_type():
    test_case = MagicMock(tc.TestCase)
    return_value = vri.VariableReferenceImpl(test_case, int)
    first = arts.DuckMockArtificialStatement(test_case, return_value)
    other = arts.DuckMockArtificialStatement(test_case, return_value)
    assert first.__eq__(other)


def test_duck_mock_hash(duck_mock_statement):
    assert duck_mock_statement.__hash__() != 0
