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

import pynguin.testcase.statements.primitivestatements as prim
import pynguin.testcase.testcase as tc


@pytest.mark.parametrize(
    "statement_type,test_case,value",
    [
        pytest.param(prim.IntPrimitiveStatement, MagicMock(tc.TestCase), 42),
        pytest.param(prim.FloatPrimitiveStatement, MagicMock(tc.TestCase), 42.23),
        pytest.param(prim.StringPrimitiveStatement, MagicMock(tc.TestCase), "foo"),
        pytest.param(prim.BooleanPrimitiveStatement, MagicMock(tc.TestCase), True),
    ],
)
def test_primitive_statement_value(statement_type, test_case, value):
    statement = statement_type(test_case, value)
    assert statement.value == value


@pytest.mark.parametrize(
    "statement_type,test_case,value,new_value",
    [
        pytest.param(prim.IntPrimitiveStatement, MagicMock(tc.TestCase), 42, 23),
        pytest.param(prim.FloatPrimitiveStatement, MagicMock(tc.TestCase), 2.1, 1.2),
        pytest.param(
            prim.StringPrimitiveStatement, MagicMock(tc.TestCase), "foo", "bar"
        ),
        pytest.param(
            prim.BooleanPrimitiveStatement, MagicMock(tc.TestCase), True, False
        ),
    ],
)
def test_primitive_statement_set_value(statement_type, test_case, value, new_value):
    statement = statement_type(test_case, value)
    statement.value = new_value
    assert statement.value == new_value


@pytest.mark.parametrize(
    "statement_type,test_case,new_test_case,value",
    [
        pytest.param(
            prim.IntPrimitiveStatement,
            MagicMock(tc.TestCase),
            MagicMock(tc.TestCase),
            42,
        ),
        pytest.param(
            prim.FloatPrimitiveStatement,
            MagicMock(tc.TestCase),
            MagicMock(tc.TestCase),
            42.23,
        ),
        pytest.param(
            prim.StringPrimitiveStatement,
            MagicMock(tc.TestCase),
            MagicMock(tc.TestCase),
            "foo",
        ),
        pytest.param(
            prim.BooleanPrimitiveStatement,
            MagicMock(tc.TestCase),
            MagicMock(tc.TestCase),
            True,
        ),
    ],
)
def test_primitive_statement_clone(statement_type, test_case, new_test_case, value):
    statement = statement_type(test_case, value)
    new_statement = statement.clone(new_test_case)
    assert new_statement.test_case == new_test_case
    assert (
        new_statement.return_value.variable_type == statement.return_value.variable_type
    )
    assert new_statement.value == statement.value


@pytest.mark.parametrize(
    "statement_type,test_case,value,visitor_method",
    [
        pytest.param(prim.IntPrimitiveStatement, MagicMock(tc.TestCase), 42, "visit_int_primitive_statement"),
        pytest.param(prim.FloatPrimitiveStatement, MagicMock(tc.TestCase), 2.1, "visit_float_primitive_statement"),
        pytest.param(
            prim.StringPrimitiveStatement, MagicMock(tc.TestCase), "foo", "visit_string_primitive_statement"
        ),
        pytest.param(
            prim.BooleanPrimitiveStatement, MagicMock(tc.TestCase), True, "visit_boolean_primitive_statement"
        ),
    ],
)
def test_primitive_statement_accept(statement_type,test_case,value, visitor_method):
    stmt = statement_type(test_case, value)
    visitor = MagicMock()
    stmt.accept(visitor)
    getattr(visitor, visitor_method).assert_called_once_with(stmt)

