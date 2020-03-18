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

import pytest

import pynguin.testcase.statements.statement as stmt
import pynguin.testcase.testcase as tc
import pynguin.testcase.variable.variablereferenceimpl as vri


def test_getters(test_case_mock):
    ref = vri.VariableReferenceImpl(test_case_mock, int)
    assert ref.variable_type == int
    assert ref.test_case == test_case_mock


def test_setters(test_case_mock):
    ref = vri.VariableReferenceImpl(test_case_mock, int)
    vt_new = float
    ref.variable_type = vt_new
    assert ref.variable_type == vt_new


def test_clone(test_case_mock):
    orig_ref = vri.VariableReferenceImpl(test_case_mock, int)
    orig_statement = MagicMock(stmt.Statement)
    orig_statement.return_value = orig_ref
    test_case_mock.statements = [orig_statement]

    new_test_case = MagicMock(tc.TestCase)
    new_ref = vri.VariableReferenceImpl(new_test_case, int)
    new_statement = MagicMock(stmt.Statement)
    new_statement.return_value = new_ref
    new_test_case.get_statement.return_value = new_statement

    clone = orig_ref.clone(new_test_case)
    assert clone is new_ref


def test_clone_with_offset(test_case_mock):
    orig_ref = vri.VariableReferenceImpl(test_case_mock, int)
    orig_statement = MagicMock(stmt.Statement)
    orig_statement.return_value = orig_ref
    test_case_mock.statements = [orig_statement]

    new_test_case = MagicMock(tc.TestCase)
    new_test_case.get_statement.return_value = MagicMock(stmt.Statement)
    orig_ref.clone(new_test_case, 5)
    new_test_case.get_statement.assert_called_once_with(5)


def test_get_position(test_case_mock):
    ref = vri.VariableReferenceImpl(test_case_mock, int)
    ref._test_case = test_case_mock
    statement = MagicMock(stmt.Statement)
    statement.return_value = ref
    test_case_mock.statements = [statement]
    assert ref.get_statement_position() == 0


def test_get_position_no_statements(test_case_mock):
    ref = vri.VariableReferenceImpl(test_case_mock, int)
    test_case_mock.statements = []
    with pytest.raises(Exception):
        ref.get_statement_position()


def test_hash(test_case_mock):
    ref = vri.VariableReferenceImpl(test_case_mock, int)
    assert ref.__hash__() != 0


def test_eq_same(test_case_mock):
    ref = vri.VariableReferenceImpl(test_case_mock, int)
    assert ref.__eq__(ref)


def test_eq_other_type(test_case_mock):
    ref = vri.VariableReferenceImpl(test_case_mock, int)
    assert not ref.__eq__(test_case_mock)


def test_distance(test_case_mock):
    ref = vri.VariableReferenceImpl(test_case_mock, int)
    assert ref.distance == 0
    ref.distance = 42
    assert ref.distance == 42


@pytest.mark.parametrize(
    "type_,result", [pytest.param(int, True), pytest.param(MagicMock, False),],
)
def test_is_primitive(test_case_mock, type_, result):
    ref = vri.VariableReferenceImpl(test_case_mock, type_)
    assert ref.is_primitive() == result


@pytest.mark.parametrize(
    "type_,result", [pytest.param(None, True), pytest.param(MagicMock, False),],
)
def test_is_type_unknown(test_case_mock, type_, result):
    ref = vri.VariableReferenceImpl(test_case_mock, type_)
    assert ref.is_type_unknown() == result


@pytest.mark.parametrize(
    "type_,result", [pytest.param(type(None), True), pytest.param(MagicMock, False),],
)
def test_is_none_type(test_case_mock, type_, result):
    ref = vri.VariableReferenceImpl(test_case_mock, type_)
    assert ref.is_none_type() == result
