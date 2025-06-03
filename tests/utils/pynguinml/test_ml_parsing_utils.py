#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import math

import numpy as np
import pytest

import pynguin.utils.pynguinml.ml_parsing_utils as mlpu

from pynguin.utils.exceptions import ConstraintValidationError


@pytest.fixture
def mock_config(monkeypatch):
    def set_mock(**kwargs):
        for attr, value in kwargs.items():
            monkeypatch.setattr(mlpu.config.configuration.pynguinml, attr, value)

    return set_mock


def test_ndim_values(monkeypatch):
    mlpu.ndim_values.cache_clear()
    monkeypatch.setattr(mlpu.config.configuration.pynguinml, "max_ndim", 3)

    actual = mlpu.ndim_values()

    assert actual == [0, 1, 2, 3]


def test_str_is_number():
    assert mlpu.str_is_number("42") is True
    assert mlpu.str_is_number("3.14") is True
    assert mlpu.str_is_number("inf") is True
    assert mlpu.str_is_number("-inf") is True
    assert mlpu.str_is_number("not_a_number") is False


def test_convert_to_num():
    result = mlpu.convert_to_num("42")
    assert result == 42
    assert isinstance(result, int)

    result = mlpu.convert_to_num("22.2")
    assert result == 22.2
    assert isinstance(result, float)

    result = mlpu.convert_to_num("inf")
    assert result == np.inf

    result = mlpu.convert_to_num("-inf")
    assert result == -np.inf

    with pytest.raises(ValueError, match="Invalid numeric string"):
        mlpu.convert_to_num("not_a_number")


def test_parse_var_dependency_with_ampersand():
    remainder, ref, is_var = mlpu.parse_var_dependency("&var+2")
    assert remainder == "+2"
    assert ref == "var"
    assert is_var is True


def test_parse_var_dependency_without_ampersand():
    remainder, ref, is_var = mlpu.parse_var_dependency("var")
    assert not remainder
    assert ref == "var"
    assert is_var is False


def test_parse_var_dependency_with_split_string():
    remainder, ref, is_var = mlpu.parse_var_dependency("shape:&size*3", "shape:")
    assert remainder == "*3"
    assert ref == "size"
    assert is_var is True


@pytest.mark.parametrize("invalid_input", ["@var", " var", "#size", " ", ""])
def test_parse_var_dependency_invalid(invalid_input):
    with pytest.raises(ConstraintValidationError):
        mlpu.parse_var_dependency(invalid_input)


@pytest.mark.parametrize(
    "valid_input, expected_output",
    [
        (">5", (None, False)),
        (">=10", (None, False)),
        ("<&abc", ("abc", True)),
        ("<=&abc", ("abc", True)),
    ],
)
def test_parse_unequal_signs_valid(valid_input, expected_output):
    assert mlpu.parse_unequal_signs(valid_input) == expected_output


@pytest.mark.parametrize("invalid_input", ["=", ">", "<=", "abc"])
def test_parse_unequal_signs_invalid(invalid_input):
    with pytest.raises(ConstraintValidationError):
        mlpu.parse_unequal_signs(invalid_input)


@pytest.mark.parametrize(
    "start_idx, text, stop_chars, expected_output",
    [
        (0, "hello world", "", ("helloworld", 11)),
        (5, "hello world", "", ("world", 11)),
        (0, "hello, world!", ",", ("hello", 6)),
        (7, "hello, world!", "!", ("world", 13)),
        (0, "  hello", "", ("hello", 7)),
    ],
)
def test_parse_until_valid(start_idx, text, stop_chars, expected_output):
    assert mlpu.parse_until(start_idx, text, stop_chars) == expected_output


@pytest.mark.parametrize(
    "start_idx, text",
    [
        (50, "short"),
        (-5, "hi"),
    ],
)
def test_parse_until_invalid(start_idx, text):
    with pytest.raises(ValueError):  # noqa: PT011
        mlpu.parse_until(start_idx, text)


@pytest.mark.parametrize(
    "tok, expected_output",
    [
        (">5", (">", 5)),
        (">=5", (">", 4)),
        ("<5", ("<", 5)),
        ("<=5", ("<", 6)),
    ],
)
def test_parse_shape_bound_valid(tok, expected_output):
    assert mlpu.parse_shape_bound(tok) == expected_output


@pytest.mark.parametrize(
    "tok",
    [
        ">",
        "<",  # Too short
        "=5",
        "abc",
        "<=abc",  # Invalid tokens
    ],
)
def test_parse_shape_bound_invalid(tok):
    with pytest.raises(ValueError):  # noqa: PT011
        mlpu.parse_shape_bound(tok)


def test_get_default_range_float32():
    low, high = mlpu.get_default_range("float32")
    assert low == np.finfo("float32").min
    assert high == np.finfo("float32").max

    low, high = mlpu.get_default_range("float64")
    assert low == np.finfo("float64").min
    assert high == np.finfo("float64").max

    low, high = mlpu.get_default_range("int32")
    assert math.isclose(low, float(np.iinfo("int32").min))
    assert math.isclose(high, float(np.iinfo("int32").max))

    low, high = mlpu.get_default_range("int64")
    assert math.isclose(low, float(np.iinfo("int64").min))
    assert math.isclose(high, float(np.iinfo("int64").max))

    with pytest.raises(ValueError, match="Invalid NumPy dtype: not_a_dtype"):
        mlpu.get_default_range("not_a_dtype")

    with pytest.raises(ValueError, match="Cannot get range for dtype bool"):
        mlpu.get_default_range("bool")


def test_pick_all_integer_types_signed_and_unsigned():
    dtype_list = ["int8", "int16", "uint8", "float32"]
    result = mlpu.pick_all_integer_types(dtype_list)
    assert result == ["int8", "int16", "uint8"]


def test_pick_all_integer_types_only_unsigned():
    dtype_list = ["int8", "int16", "uint8", "float32"]
    result = mlpu.pick_all_integer_types(dtype_list, only_unsigned=True)
    assert result == ["uint8"]


def test_pick_all_integer_types_no_matches():
    dtype_list = ["float32", "float64"]
    result = mlpu.pick_all_integer_types(dtype_list)
    assert result == []

    dtype_list = ["random", "42"]
    result = mlpu.pick_all_integer_types(dtype_list)
    assert result == []

    result = mlpu.pick_all_integer_types([])
    assert result == []


def test_pick_all_float_types():
    dtypes = ["float16", "float32", "float64"]
    result = mlpu.pick_all_float_types(dtypes)
    assert result == ["float16", "float32", "float64"]

    dtypes = ["int8", "float32", "float64", "uint32", "str"]
    result = mlpu.pick_all_float_types(dtypes)
    assert result == ["float32", "float64"]

    dtypes = ["int32", "uint8", "bool", "str"]
    result = mlpu.pick_all_float_types(dtypes)
    assert result == []

    result = mlpu.pick_all_float_types([])
    assert result == []


def test_pick_scalar_types():
    dtypes = ["int8", "float32", "uint64", "float64", "bool", "str"]
    result = mlpu.pick_scalar_types(dtypes)
    assert result == ["int8", "uint64", "float32", "float64"]


def test_infer_type_from_str():
    assert mlpu._infer_type_from_str("42") == "int"
    assert mlpu._infer_type_from_str("3.14") == "float"
    assert mlpu._infer_type_from_str("true") == "bool"
    assert mlpu._infer_type_from_str("hello") == "str"


@pytest.mark.parametrize(
    "values, expected",
    [
        (["42", "-7", "0"], [42, -7, 0]),  # Integers
        (["3.1", "-0.001", "1e3"], [3.1, -0.001, 1000.0]),  # Floats
        (["True", "False", "true"], [True, False, True]),  # Booleans
        (["hello", "world", "42a", "3.14.5"], ["hello", "world", "42a", "3.14.5"]),  # Strings
        (["42", "3.1", "True", "hello"], [42, 3.1, True, "hello"]),  # Mixed types
        ([], []),  # Empty list
        ([" 42 ", " 3.1 ", " True "], [42, 3.1, True]),  # Whitespace handling
    ],
)
def test_convert_values(values, expected):
    assert mlpu.convert_values(values) == expected


@pytest.mark.parametrize(
    "type_str, expected",
    [
        ("int", int),
        ("float", float),
        ("bool", bool),
        ("complex", complex),
        ("str", str),
        ("int32", int),
        ("int64", int),
        ("float32", float),
        ("float64", float),
        ("complex128", complex),
        ("bool_", bool),
    ],
)
def test_convert_str_to_type_valid(type_str, expected):
    assert mlpu.convert_str_to_type(type_str) == expected


@pytest.mark.parametrize("invalid_type", ["unknown_type", "xyz123", "", "datetime64"])
def test_convert_str_to_type_invalid(invalid_type):
    with pytest.raises(ValueError):  # noqa: PT011
        mlpu.convert_str_to_type(invalid_type)


@pytest.mark.parametrize(
    "array, expected_shape",
    [
        ([1, 2, 3], [3]),
        ([[[1], [2]], [[3], [4]], [[5], [6]]], [3, 2, 1]),
        ([], [0]),
        ([[], []], [2, 0]),
    ],
)
def test_get_shape(array, expected_shape):
    assert mlpu.get_shape(array) == expected_shape
