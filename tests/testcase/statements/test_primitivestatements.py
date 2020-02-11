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
from unittest import mock
from unittest.mock import MagicMock

import pytest

import pynguin.testcase.statements.primitivestatements as prim
import pynguin.testcase.testcase as tc
import pynguin.configuration as config


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
        pytest.param(
            prim.IntPrimitiveStatement,
            MagicMock(tc.TestCase),
            42,
            "visit_int_primitive_statement",
        ),
        pytest.param(
            prim.FloatPrimitiveStatement,
            MagicMock(tc.TestCase),
            2.1,
            "visit_float_primitive_statement",
        ),
        pytest.param(
            prim.StringPrimitiveStatement,
            MagicMock(tc.TestCase),
            "foo",
            "visit_string_primitive_statement",
        ),
        pytest.param(
            prim.BooleanPrimitiveStatement,
            MagicMock(tc.TestCase),
            True,
            "visit_boolean_primitive_statement",
        ),
    ],
)
def test_primitive_statement_accept(statement_type, test_case, value, visitor_method):
    stmt = statement_type(test_case, value)
    visitor = MagicMock()
    stmt.accept(visitor)
    getattr(visitor, visitor_method).assert_called_once_with(stmt)


@pytest.mark.parametrize(
    "statement_type,value",
    [
        pytest.param(prim.IntPrimitiveStatement, 42),
        pytest.param(prim.FloatPrimitiveStatement, 42.23),
        pytest.param(prim.StringPrimitiveStatement, "foo"),
        pytest.param(prim.BooleanPrimitiveStatement, True),
    ],
)
def test_primitive_statement_equals_same(statement_type, value):
    test_case = MagicMock(tc.TestCase)
    statement = statement_type(test_case, value)
    assert statement.__eq__(statement)


@pytest.mark.parametrize(
    "statement_type,value",
    [
        pytest.param(prim.IntPrimitiveStatement, 42),
        pytest.param(prim.FloatPrimitiveStatement, 42.23),
        pytest.param(prim.StringPrimitiveStatement, "foo"),
        pytest.param(prim.BooleanPrimitiveStatement, True),
    ],
)
def test_primitive_statement_equals_other_type(statement_type, value):
    test_case = MagicMock(tc.TestCase)
    statement = statement_type(test_case, value)
    assert not statement.__eq__(test_case)


@pytest.mark.parametrize(
    "statement_type,value",
    [
        pytest.param(prim.IntPrimitiveStatement, 42),
        pytest.param(prim.FloatPrimitiveStatement, 42.23),
        pytest.param(prim.StringPrimitiveStatement, "foo"),
        pytest.param(prim.BooleanPrimitiveStatement, True),
    ],
)
def test_primitive_statement_equals_clone(statement_type, value):
    test_case = MagicMock(tc.TestCase)
    statement = statement_type(test_case, value)
    test_case.statements = [statement]
    test_case2 = MagicMock(tc.TestCase)
    clone = statement.clone(test_case2)
    test_case2.statements = [clone]
    assert statement.__eq__(clone)


def test_none_statement_equals_clone():
    test_case = MagicMock(tc.TestCase)
    statement = prim.NoneStatement(test_case, type(None))
    test_case.statements = [statement]
    test_case2 = MagicMock(tc.TestCase)
    clone = statement.clone(test_case2)
    test_case2.statements = [clone]
    assert statement.__eq__(clone)


@pytest.mark.parametrize(
    "statement_type,value",
    [
        pytest.param(prim.IntPrimitiveStatement, 42),
        pytest.param(prim.FloatPrimitiveStatement, 42.23),
        pytest.param(prim.StringPrimitiveStatement, "foo"),
        pytest.param(prim.BooleanPrimitiveStatement, True),
    ],
)
def test_primitive_statement_hash(statement_type, value):
    statement = statement_type(MagicMock(tc.TestCase), value)
    assert statement.__hash__() != 0


def test_int_primitive_statement_randomize_value(test_case_mock):
    statement = prim.IntPrimitiveStatement(test_case_mock)
    statement.randomize_value()
    assert isinstance(statement.value, int)


def test_float_primitive_statement_randomize_value(test_case_mock):
    statement = prim.FloatPrimitiveStatement(test_case_mock)
    statement.randomize_value()
    assert isinstance(statement.value, float)


def test_bool_primitive_statement_randomize_value(test_case_mock):
    statement = prim.BooleanPrimitiveStatement(test_case_mock)
    statement.randomize_value()
    assert statement.value or not statement.value


def test_string_primitive_statement_randomize_value(test_case_mock):
    statement = prim.StringPrimitiveStatement(test_case_mock)
    statement.randomize_value()
    assert 0 <= len(statement.value) <= config.INSTANCE.string_length


def test_none_statement_randomize_value(test_case_mock):
    statement = prim.NoneStatement(test_case_mock, type(None))
    statement.randomize_value()
    assert statement.value is None


def test_string_primitive_statement_random_deletion(test_case_mock):
    sample = list("Test")
    result = prim.StringPrimitiveStatement._random_deletion(sample)
    assert len(result) <= len(sample)


def test_string_primitive_statement_random_insertion(test_case_mock):
    sample = list("Test")
    result = prim.StringPrimitiveStatement._random_insertion(sample)
    assert len(result) >= len(sample)


def test_string_primitive_statement_random_insertion_empty(test_case_mock):
    sample = list("")
    result = prim.StringPrimitiveStatement._random_insertion(sample)
    assert len(result) >= len(sample)


def test_string_primitive_statement_random_replacement(test_case_mock):
    sample = list("Test")
    result = prim.StringPrimitiveStatement._random_replacement(sample)
    assert len(result) == len(sample)


def test_string_primitive_statement_delta_none(test_case_mock):
    value = "t"
    statement = prim.StringPrimitiveStatement(test_case_mock, value)
    with mock.patch("pynguin.utils.randomness.next_float") as float_mock:
        float_mock.side_effect = [1.0, 1.0, 1.0]
        statement.delta()
        assert statement.value == value


def test_string_primitive_statement_delta_all(test_case_mock):
    value = "te"
    statement = prim.StringPrimitiveStatement(test_case_mock, value)
    with mock.patch("pynguin.utils.randomness.next_char") as char_mock:
        char_mock.side_effect = ["a", "b"]
        with mock.patch("pynguin.utils.randomness.next_int") as int_mock:
            int_mock.return_value = 0
            with mock.patch("pynguin.utils.randomness.next_float") as float_mock:
                deletion = [0.0, 0.0, 1.0]
                replacement = [0.0, 0.0]
                insertion = [0.0, 0.0, 1.0]
                float_mock.side_effect = deletion + replacement + insertion
                statement.delta()
                assert statement.value == "ba"


def test_int_primitive_statement_delta(test_case_mock):
    config.INSTANCE.max_delta = 10
    statement = prim.IntPrimitiveStatement(test_case_mock, 1)
    with mock.patch("pynguin.utils.randomness.next_gaussian") as gauss_mock:
        gauss_mock.return_value = 0.5
        statement.delta()
    assert statement.value == 6


def test_float_primitive_statement_delta_max(test_case_mock):
    config.INSTANCE.max_delta = 10
    statement = prim.FloatPrimitiveStatement(test_case_mock, 1.5)
    with mock.patch("pynguin.utils.randomness.next_gaussian") as gauss_mock:
        gauss_mock.return_value = 0.5
        with mock.patch("pynguin.utils.randomness.next_float") as float_mock:
            float_mock.return_value = 0.0
            statement.delta()
            assert statement.value == 6.5


def test_float_primitive_statement_delta_gauss(test_case_mock):
    config.INSTANCE.max_delta = 10
    statement = prim.FloatPrimitiveStatement(test_case_mock, 1.0)
    with mock.patch("pynguin.utils.randomness.next_gaussian") as gauss_mock:
        gauss_mock.return_value = 0.5
        with mock.patch("pynguin.utils.randomness.next_float") as float_mock:
            float_mock.return_value = 1.0 / 3.0
            statement.delta()
            assert statement.value == 1.5


def test_float_primitive_statement_delta_round(test_case_mock):
    statement = prim.FloatPrimitiveStatement(test_case_mock, 1.2345)
    with mock.patch("pynguin.utils.randomness.next_int") as int_mock:
        int_mock.return_value = 2
        with mock.patch("pynguin.utils.randomness.next_float") as float_mock:
            float_mock.return_value = 2.0 / 3.0
            statement.delta()
            assert statement.value == 1.23


def test_boolean_primitive_statement_delta(test_case_mock):
    statement = prim.BooleanPrimitiveStatement(test_case_mock, True)
    statement.delta()
    assert not statement.value


def test_primitive_statement_mutate(test_case_mock):
    statement = prim.BooleanPrimitiveStatement(test_case_mock, True)
    statement.mutate()
    assert not statement.value
