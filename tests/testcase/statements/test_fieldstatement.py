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

import pynguin.testcase.statements.fieldstatement as fstmt
import pynguin.testcase.testcase as tc


def test_field_statement(test_case_mock, variable_reference_mock):
    field_statement = fstmt.FieldStatement(
        test_case_mock, "test", str, variable_reference_mock
    )
    assert field_statement.field == "test"


def test_field_statement_source(test_case_mock, variable_reference_mock):
    field_statement = fstmt.FieldStatement(
        test_case_mock, "test", str, variable_reference_mock
    )
    field_statement.field = "another"
    assert field_statement.field == "another"


def test_field_statement_eq_same(test_case_mock, variable_reference_mock):
    statement = fstmt.FieldStatement(
        test_case_mock, "test", str, variable_reference_mock
    )
    assert statement.__eq__(statement)


def test_field_statement_eq_other_type(test_case_mock, variable_reference_mock):
    statement = fstmt.FieldStatement(
        test_case_mock, "test", str, variable_reference_mock
    )
    assert not statement.__eq__(variable_reference_mock)


def test_field_statement_eq_clone(test_case_mock, variable_reference_mock):
    statement = fstmt.FieldStatement(
        test_case_mock, "test", str, variable_reference_mock
    )
    clone = statement.clone(MagicMock(tc.TestCase))
    assert statement.__eq__(clone)
