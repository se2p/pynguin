#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import math

import pytest

import pynguin.utils.pynguinml.ml_parsing_utils as mlpu

from pynguin.utils.exceptions import ConstraintValidationError


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


@pytest.mark.parametrize(
    "values, expected",
    [
        (["42", "-7", "0"], [42, -7, 0]),  # Integers
        (["3.14", "-0.001", "1e3"], [math.pi, -0.001, 1000.0]),  # Floats
        (["True", "False", "true"], [True, False, True]),  # Booleans
        (["hello", "world", "42a", "3.14.5"], ["hello", "world", "42a", "3.14.5"]),  # Strings
        (["42", "3.14", "True", "hello"], [42, math.pi, True, "hello"]),  # Mixed types
        ([], []),  # Empty list
        ([" 42 ", " 3.14 ", " True "], [42, math.pi, True]),  # Whitespace handling
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


@pytest.mark.parametrize("invalid_type", ["unknown_type", "xyz123", ""])
def test_convert_str_to_type_invalid(invalid_type):
    with pytest.raises(ValueError, match=f"Unknown type: {invalid_type}"):
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
