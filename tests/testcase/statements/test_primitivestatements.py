#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
from unittest import mock
from unittest.mock import MagicMock

import pytest

import pynguin.configuration as config
import pynguin.testcase.statement as stmt
import pynguin.testcase.testcase as tc
import pynguin.testcase.variablereference as vr

from pynguin.analyses.constants import ConstantPool
from pynguin.analyses.constants import DelegatingConstantProvider
from pynguin.analyses.constants import EmptyConstantProvider


@pytest.mark.parametrize(
    "statement_type,value",
    [
        (stmt.IntPrimitiveStatement, 42),
        (stmt.FloatPrimitiveStatement, 42.23),
        (stmt.StringPrimitiveStatement, "foo"),
        (stmt.BytesPrimitiveStatement, b"test"),
        (stmt.BooleanPrimitiveStatement, True),
        (stmt.ComplexPrimitiveStatement, 4 + 3j),
    ],
)
def test_primitive_statement_value(statement_type, default_test_case, value):
    statement = statement_type(default_test_case, value)
    assert statement.value == value


@pytest.mark.parametrize(
    "statement_type,value",
    [
        (stmt.IntPrimitiveStatement, 42),
        (stmt.FloatPrimitiveStatement, 42.23),
        (stmt.StringPrimitiveStatement, "foo"),
        (stmt.BytesPrimitiveStatement, b"test"),
        (stmt.ComplexPrimitiveStatement, 4 + 3j),
    ],
)
def test_primitive_statement_value_from_seeding(statement_type, default_test_case, value):
    config.configuration.seeding.seeded_primitives_reuse_probability = 1.0
    pool = ConstantPool()
    pool.add_constant(value)
    provider = DelegatingConstantProvider(
        pool=pool, delegate=EmptyConstantProvider(), probability=1.0
    )
    statement = statement_type(default_test_case, constant_provider=provider)
    assert statement.value == value


@pytest.mark.parametrize(
    "statement_type",
    [
        stmt.IntPrimitiveStatement,
        stmt.FloatPrimitiveStatement,
        stmt.StringPrimitiveStatement,
        stmt.BytesPrimitiveStatement,
        stmt.BooleanPrimitiveStatement,
        stmt.ComplexPrimitiveStatement,
        stmt.ClassPrimitiveStatement,
    ],
)
def test_primitive_statement_value_none(statement_type, default_test_case):
    statement = statement_type(default_test_case, None)
    assert statement.value is not None


@pytest.mark.parametrize(
    "statement_type,value,new_value",
    [
        (stmt.IntPrimitiveStatement, 42, 23),
        (stmt.FloatPrimitiveStatement, 2.1, 1.2),
        (stmt.StringPrimitiveStatement, "foo", "bar"),
        (stmt.BytesPrimitiveStatement, b"foo", b"bar"),
        (stmt.BooleanPrimitiveStatement, True, False),
        (stmt.ComplexPrimitiveStatement, 4 + 1j, 1 + 4j),
        (stmt.ClassPrimitiveStatement, 0, 1),
    ],
)
def test_primitive_statement_set_value(statement_type, default_test_case, value, new_value):
    statement = statement_type(default_test_case, value)
    statement.value = new_value
    assert statement.value == new_value


@pytest.mark.parametrize(
    "statement_type,value",
    [
        (
            stmt.IntPrimitiveStatement,
            42,
        ),
        (
            stmt.FloatPrimitiveStatement,
            42.23,
        ),
        (
            stmt.StringPrimitiveStatement,
            "foo",
        ),
        (
            stmt.BytesPrimitiveStatement,
            b"foo",
        ),
        (
            stmt.BooleanPrimitiveStatement,
            True,
        ),
        (
            stmt.ComplexPrimitiveStatement,
            4 + 1j,
        ),
        (
            stmt.ClassPrimitiveStatement,
            0,
        ),
    ],
)
def test_primitive_statement_clone(statement_type, default_test_case, value):
    statement = statement_type(default_test_case, value)
    clone_case = default_test_case.clone()
    new_statement = statement.clone(clone_case, {})
    assert new_statement.test_case == clone_case
    assert new_statement.ret_val.type == statement.ret_val.type
    assert new_statement.value == statement.value


@pytest.mark.parametrize(
    "statement_type,value,visitor_method",
    [
        (
            stmt.IntPrimitiveStatement,
            42,
            "visit_int_primitive_statement",
        ),
        (
            stmt.FloatPrimitiveStatement,
            2.1,
            "visit_float_primitive_statement",
        ),
        (
            stmt.StringPrimitiveStatement,
            "foo",
            "visit_string_primitive_statement",
        ),
        (
            stmt.BytesPrimitiveStatement,
            b"foo",
            "visit_bytes_primitive_statement",
        ),
        (
            stmt.BooleanPrimitiveStatement,
            True,
            "visit_boolean_primitive_statement",
        ),
        (
            stmt.ComplexPrimitiveStatement,
            4 + 1j,
            "visit_complex_primitive_statement",
        ),
        (
            stmt.ClassPrimitiveStatement,
            0,
            "visit_class_primitive_statement",
        ),
    ],
)
def test_primitive_statement_accept(statement_type, default_test_case, value, visitor_method):
    stmt = statement_type(default_test_case, value)
    visitor = MagicMock()
    stmt.accept(visitor)
    getattr(visitor, visitor_method).assert_called_once_with(stmt)


@pytest.mark.parametrize(
    "statement_type,value",
    [
        (stmt.IntPrimitiveStatement, 42),
        (stmt.FloatPrimitiveStatement, 42.23),
        (stmt.StringPrimitiveStatement, "foo"),
        (stmt.BytesPrimitiveStatement, b"foo"),
        (stmt.BooleanPrimitiveStatement, True),
        (stmt.ComplexPrimitiveStatement, 4 + 1j),
        (stmt.ClassPrimitiveStatement, 0),
    ],
)
def test_primitive_statement_equals_same(statement_type, default_test_case, value):
    statement = statement_type(default_test_case, value)
    assert statement == statement  # noqa: PLR0124


@pytest.mark.parametrize(
    "statement_type,value",
    [
        (stmt.IntPrimitiveStatement, 42),
        (stmt.FloatPrimitiveStatement, 42.23),
        (stmt.StringPrimitiveStatement, "foo"),
        (stmt.BytesPrimitiveStatement, b"foo"),
        (stmt.BooleanPrimitiveStatement, True),
        (stmt.ComplexPrimitiveStatement, 4 + 1j),
        (stmt.ClassPrimitiveStatement, 0),
    ],
)
def test_primitive_statement_equals_other_type(statement_type, default_test_case, value):
    statement = statement_type(default_test_case, value)
    assert not statement.structural_eq(default_test_case, {})


@pytest.mark.parametrize(
    "statement_type,value",
    [
        (stmt.IntPrimitiveStatement, 42),
        (stmt.FloatPrimitiveStatement, 42.23),
        (stmt.StringPrimitiveStatement, "foo"),
        (stmt.BytesPrimitiveStatement, b"foo"),
        (stmt.BooleanPrimitiveStatement, True),
        (stmt.ComplexPrimitiveStatement, 4 + 1j),
        (stmt.ClassPrimitiveStatement, 0),
    ],
)
def test_primitive_statement_equals_clone(statement_type, default_test_case, value):
    cloned_case = default_test_case.clone()
    statement = statement_type(default_test_case, value)
    default_test_case.add_statement(statement)
    clone = statement.clone(cloned_case, {})
    assert statement.structural_eq(clone, {statement.ret_val: clone.ret_val})


def test_none_statement_equals_clone():
    test_case = MagicMock(tc.TestCase)
    statement = stmt.NoneStatement(test_case)
    test_case.statements = [statement]
    test_case2 = MagicMock(tc.TestCase)
    clone = statement.clone(test_case2, {})
    assert statement.structural_eq(clone, {statement.ret_val: clone.ret_val})


@pytest.mark.parametrize(
    "statement_type,value",
    [
        (stmt.IntPrimitiveStatement, 42),
        (stmt.FloatPrimitiveStatement, 42.23),
        (stmt.StringPrimitiveStatement, "foo"),
        (stmt.BytesPrimitiveStatement, b"foo"),
        (stmt.BooleanPrimitiveStatement, True),
        (stmt.ComplexPrimitiveStatement, 4 + 1j),
        (stmt.ClassPrimitiveStatement, 0),
    ],
)
def test_primitive_statement_hash(statement_type, default_test_case, value):
    statement = statement_type(default_test_case, value)
    assert statement.structural_hash({statement.ret_val: 0}) != 0


def test_int_primitive_statement_randomize_value(default_test_case):
    statement = stmt.IntPrimitiveStatement(default_test_case)
    statement.randomize_value()
    assert isinstance(statement.value, int)


def test_float_primitive_statement_randomize_value(default_test_case):
    statement = stmt.FloatPrimitiveStatement(default_test_case)
    statement.randomize_value()
    assert isinstance(statement.value, float)


def test_complex_primitive_statement_randomize_value(default_test_case):
    statement = stmt.ComplexPrimitiveStatement(default_test_case)
    statement.randomize_value()
    assert isinstance(statement.value, complex)


def test_bool_primitive_statement_randomize_value(default_test_case):
    statement = stmt.BooleanPrimitiveStatement(default_test_case)
    statement.randomize_value()
    assert statement.value or not statement.value


def test_string_primitive_statement_randomize_value(default_test_case):
    statement = stmt.StringPrimitiveStatement(default_test_case)
    statement.randomize_value()
    assert len(statement.value) <= config.configuration.test_creation.string_length


def test_bytes_primitive_statement_randomize_value(default_test_case):
    statement = stmt.BytesPrimitiveStatement(default_test_case)
    statement.randomize_value()
    assert len(statement.value) <= config.configuration.test_creation.bytes_length
    assert isinstance(statement.value, bytes)


def test_none_statement_randomize_value(default_test_case):
    statement = stmt.NoneStatement(default_test_case)
    statement.randomize_value()
    assert statement.value is None


def test_none_statement_delta(test_case_mock):
    statement = stmt.NoneStatement(test_case_mock)
    statement.delta()
    assert statement.value is None


def test_string_primitive_statement_random_deletion():
    sample = list("Test")
    result = stmt.StringPrimitiveStatement._random_deletion(sample)
    assert len(result) <= len(sample)


def test_string_primitive_statement_random_insertion():
    sample = list("Test")
    result = stmt.StringPrimitiveStatement._random_insertion(sample)
    assert len(result) >= len(sample)


def test_string_primitive_statement_random_insertion_empty():
    sample = list("")
    result = stmt.StringPrimitiveStatement._random_insertion(sample)
    assert len(result) >= len(sample)


def test_string_primitive_statement_random_replacement():
    sample = list("Test")
    result = stmt.StringPrimitiveStatement._random_replacement(sample)
    assert len(result) == len(sample)


def test_string_primitive_statement_delta_none(default_test_case):
    value = "t"
    statement = stmt.StringPrimitiveStatement(default_test_case, value)
    with mock.patch("pynguin.utils.randomness.next_float") as float_mock:
        float_mock.side_effect = [1.0, 1.0, 1.0]
        statement.delta()
        assert statement.value == value


def test_string_primitive_statement_delta_all(default_test_case):
    value = "te"
    statement = stmt.StringPrimitiveStatement(default_test_case, value)
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


def test_bytes_primitive_statement_random_deletion():
    sample = list(b"Test")
    result = stmt.BytesPrimitiveStatement._random_deletion(sample)
    assert len(result) <= len(sample)


def test_bytes_primitive_statement_random_insertion():
    sample = list(b"Test")
    result = stmt.BytesPrimitiveStatement._random_insertion(sample)
    assert len(result) >= len(sample)


def test_bytes_primitive_statement_random_insertion_empty():
    sample = list(b"")
    result = stmt.BytesPrimitiveStatement._random_insertion(sample)
    assert len(result) >= len(sample)


def test_bytes_primitive_statement_random_replacement():
    sample = list(b"Test")
    result = stmt.BytesPrimitiveStatement._random_replacement(sample)
    assert len(result) == len(sample)


def test_bytes_primitive_statement_delta_none(default_test_case):
    value = b"t"
    statement = stmt.BytesPrimitiveStatement(default_test_case, value)
    with mock.patch("pynguin.utils.randomness.next_float") as float_mock:
        float_mock.side_effect = [1.0, 1.0, 1.0]
        statement.delta()
        assert statement.value == value


def test_bytes_primitive_statement_delta_all(default_test_case):
    value = b"te"
    statement = stmt.BytesPrimitiveStatement(default_test_case, value)
    with mock.patch("pynguin.utils.randomness.next_byte") as char_mock:
        char_mock.side_effect = [12, 128]
        with mock.patch("pynguin.utils.randomness.next_int") as int_mock:
            int_mock.return_value = 0
            with mock.patch("pynguin.utils.randomness.next_float") as float_mock:
                deletion = [0.0, 0.0, 1.0]
                replacement = [0.0, 0.0]
                insertion = [0.0, 0.0, 1.0]
                float_mock.side_effect = deletion + replacement + insertion
                statement.delta()
                assert statement.value == b"\x80\x0c"


def test_int_primitive_statement_delta(default_test_case):
    config.configuration.test_creation.max_delta = 10
    statement = stmt.IntPrimitiveStatement(default_test_case, 1)
    with mock.patch("pynguin.utils.randomness.next_gaussian") as gauss_mock:
        gauss_mock.return_value = 0.5
        statement.delta()
    assert statement.value == 6


@pytest.mark.parametrize(
    "stmt_type,value,real_or_imag, expected",
    [
        (stmt.FloatPrimitiveStatement, 1.5, None, 6.5),
        (stmt.ComplexPrimitiveStatement, 1.5 + 1j, True, 6.5 + 1j),
        (stmt.ComplexPrimitiveStatement, 1.5 + 1j, False, 1.5 + 6j),
    ],
)
def test_float_complex_primitive_statement_delta_max(
    default_test_case, stmt_type, value, real_or_imag, expected
):
    config.configuration.test_creation.max_delta = 10
    statement = stmt_type(default_test_case, value)
    with mock.patch("pynguin.utils.randomness.next_gaussian") as gauss_mock:
        gauss_mock.return_value = 0.5
        with mock.patch("pynguin.utils.randomness.next_bool") as bool_mock:
            # Only relevant for complex.
            bool_mock.return_value = real_or_imag
            with mock.patch("pynguin.utils.randomness.next_float") as float_mock:
                float_mock.return_value = 0.0
                statement.delta()
                assert statement.value == expected


@pytest.mark.parametrize(
    "stmt_type,value,real_or_imag, expected",
    [
        (stmt.FloatPrimitiveStatement, 1.5, None, 2.0),
        (stmt.ComplexPrimitiveStatement, 1.5 + 1j, True, 2.0 + 1j),
        (stmt.ComplexPrimitiveStatement, 1.5 + 1j, False, 1.5 + 1.5j),
    ],
)
def test_float_complex_primitive_statement_delta_gauss(
    default_test_case, stmt_type, value, real_or_imag, expected
):
    config.configuration.test_creation.max_delta = 10
    statement = stmt_type(default_test_case, value)
    with mock.patch("pynguin.utils.randomness.next_gaussian") as gauss_mock:
        gauss_mock.return_value = 0.5
        with mock.patch("pynguin.utils.randomness.next_bool") as bool_mock:
            # Only relevant for complex.
            bool_mock.return_value = real_or_imag
            with mock.patch("pynguin.utils.randomness.next_float") as float_mock:
                float_mock.return_value = 1.0 / 3.0
                statement.delta()
                assert statement.value == expected


@pytest.mark.parametrize(
    "stmt_type,value,real_or_imag, expected",
    [
        (stmt.FloatPrimitiveStatement, 1.2345, None, 1.23),
        (stmt.ComplexPrimitiveStatement, 1.2345 + 1.2345j, True, 1.23 + 1.2345j),
        (stmt.ComplexPrimitiveStatement, 1.2345 + 1.2345j, False, 1.2345 + 1.23j),
    ],
)
def test_float_complex_primitive_statement_delta_round(
    default_test_case, stmt_type, value, real_or_imag, expected
):
    statement = stmt_type(default_test_case, value)
    with mock.patch("pynguin.utils.randomness.next_int") as int_mock:
        int_mock.return_value = 2
        with mock.patch("pynguin.utils.randomness.next_bool") as bool_mock:
            # Only relevant for complex.
            bool_mock.return_value = real_or_imag
            with mock.patch("pynguin.utils.randomness.next_float") as float_mock:
                float_mock.return_value = 2.0 / 3.0
                statement.delta()
                assert statement.value == expected


def test_boolean_primitive_statement_delta(default_test_case):
    statement = stmt.BooleanPrimitiveStatement(default_test_case, True)  # noqa: FBT003
    statement.delta()
    assert not statement.value


def test_primitive_statement_mutate_delta(default_test_case):
    statement = stmt.IntPrimitiveStatement(default_test_case, 2)
    with mock.patch("pynguin.utils.randomness.next_float") as float_mock:
        float_mock.return_value = 1.0
        with mock.patch.object(statement, "delta") as rnd_mock:

            def mock_rnd():
                statement._value = 42

            rnd_mock.side_effect = mock_rnd
            statement.mutate()
            rnd_mock.assert_called_once()
            assert statement.value == 42


def test_primitive_statement_mutate_constant(default_test_case):
    statement = stmt.IntPrimitiveStatement(default_test_case, 2)
    with mock.patch("pynguin.utils.randomness.next_float") as float_mock:
        float_mock.return_value = 0.0
        with mock.patch.object(statement, "randomize_value") as rnd_mock:

            def mock_rnd():
                statement._value = 42

            rnd_mock.side_effect = mock_rnd
            statement.mutate()
            rnd_mock.assert_called_once()
            assert statement.value == 42


def test_primitive_statement_accessible(default_test_case):
    statement = stmt.IntPrimitiveStatement(default_test_case, 0)
    assert statement.accessible_object() is None


def test_primitive_statement_references(default_test_case):
    statement = stmt.IntPrimitiveStatement(default_test_case, 0)
    assert {statement.ret_val} == statement.get_variable_references()


def test_primitive_statement_replace(default_test_case, type_system):
    statement = stmt.IntPrimitiveStatement(default_test_case, 0)
    new = vr.VariableReference(default_test_case, type_system.convert_type_hint(int))
    statement.replace(statement.ret_val, new)
    assert statement.ret_val == new


def test_primitive_statement_replace_ignore(default_test_case):
    statement = stmt.IntPrimitiveStatement(default_test_case, 0)
    new = stmt.FloatPrimitiveStatement(default_test_case, 0).ret_val
    old = statement.ret_val
    statement.replace(new, new)
    assert statement.ret_val == old


def test_primitive_statement_get_position(default_test_case):
    statement = stmt.IntPrimitiveStatement(default_test_case, 5)
    default_test_case.add_statement(statement)
    assert statement.get_position() == 0


def test_primitive_statement_get_position_not_found(default_test_case):
    statement = stmt.IntPrimitiveStatement(default_test_case, 5)
    with pytest.raises(Exception):  # noqa: B017, PT011
        statement.get_position()


def test_enum_statement_accessible_object(default_test_case):
    enum_ = MagicMock(names=["FOO"])
    statement = stmt.EnumPrimitiveStatement(default_test_case, enum_)
    assert statement.accessible_object() == enum_


def test_enum_statement_value_name(test_case_mock):
    enum_ = MagicMock(names=["FOO"])
    statement = stmt.EnumPrimitiveStatement(test_case_mock, enum_)
    assert statement.value == 0
    assert statement.value_name == "FOO"


def test_enum_statement_randomize_value(test_case_mock):
    enum_ = MagicMock(names=["FOO", "BAR", "BAZ"])
    statement = stmt.EnumPrimitiveStatement(test_case_mock, enum_)
    with mock.patch("pynguin.utils.randomness.next_int") as int_mock:
        int_mock.return_value = 2
        statement.randomize_value()
        assert statement.value == 2
        assert statement.value_name == "BAZ"


def test_enum_statement_delta(test_case_mock):
    enum_ = MagicMock(names=["FOO", "BAR", "BAZ"])
    statement = stmt.EnumPrimitiveStatement(test_case_mock, enum_)
    prev = statement.value
    statement.delta()
    assert statement.value != prev
    assert 0 <= statement.value <= 2


def test_enum_statement_clone(test_case_mock):
    enum_ = MagicMock(names=["FOO", "BAR", "BAZ"])
    statement = stmt.EnumPrimitiveStatement(test_case_mock, enum_)
    clone = statement.clone(test_case_mock, {})
    assert clone.value == statement.value


def test_enum_statement_eq(default_test_case):
    enum_ = MagicMock(names=["FOO", "BAR", "BAZ"])
    statement = stmt.EnumPrimitiveStatement(default_test_case, enum_)
    test_case2 = default_test_case.clone()
    default_test_case.add_statement(statement)
    clone = statement.clone(test_case2, {})
    test_case2.add_statement(clone)
    assert statement.structural_eq(clone, {statement.ret_val: clone.ret_val})


def test_enum_statement_not_eq(default_test_case):
    enum_ = MagicMock(names=["FOO", "BAR", "BAZ"])
    statement = stmt.EnumPrimitiveStatement(default_test_case, enum_)
    test_case2 = default_test_case.clone()
    default_test_case.add_statement(statement)
    clone = statement.clone(test_case2, {})
    test_case2.add_statement(clone)
    statement._generic_enum = MagicMock()
    assert not statement.structural_eq(clone, {statement.ret_val: clone.ret_val})


def test_enum_statement_hash(test_case_mock):
    enum_ = MagicMock(names=["FOO"])
    statement = stmt.EnumPrimitiveStatement(test_case_mock, enum_)
    statement2 = stmt.EnumPrimitiveStatement(test_case_mock, enum_)
    assert statement.structural_hash({statement.ret_val: 0}) == statement2.structural_hash({
        statement2.ret_val: 0
    })


def test_enum_statement_accept(test_case_mock):
    enum_ = MagicMock(names=["FOO"])
    statement = stmt.EnumPrimitiveStatement(test_case_mock, enum_)
    visitor = MagicMock()
    statement.accept(visitor)
    visitor.visit_enum_statement.assert_called_once()


def test_class_statement_delta(default_test_case):
    statement = stmt.ClassPrimitiveStatement(default_test_case, 0)
    statement.delta()
    assert statement.value != 0
