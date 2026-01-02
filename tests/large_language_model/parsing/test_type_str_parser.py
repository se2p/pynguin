#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
"""Tests for type string parser module."""

import builtins
from unittest.mock import Mock

from pynguin.large_language_model.parsing.type_str_parser import TypeStrParser


def test_parse_none():
    """Test parsing None types."""
    parser = TypeStrParser(create_mock_type_system())
    none_type = type(None)
    assert parser.parse("None") is none_type
    assert parser.parse("NoneType") is none_type
    assert parser.parse("type(None)") is none_type


def test_parse_any():
    """Test parsing Any types."""
    parser = TypeStrParser(create_mock_type_system())
    assert parser.parse("Any") is type(builtins.object)
    assert parser.parse("typing.Any") is type(builtins.object)
    assert parser.parse("builtins.object") is type(builtins.object)


def test_parse_tuple():
    """Test parsing tuple types."""
    parser = TypeStrParser(create_mock_type_system())
    result = parser.parse("Tuple[int, str]")
    assert result is type((int, str))

    result = parser.parse("tuple[int, str]")
    assert result is type((int, str))

    result = parser.parse("typing.Tuple[int, str]")
    assert result is type((int, str))


def test_parse_list():
    """Test parsing list types."""
    parser = TypeStrParser(create_mock_type_system())
    result = parser.parse("List[int]")
    assert isinstance(result, type)
    assert result is type(list[int])  # type: ignore[comparison-overlap]

    result = parser.parse("list[int]")
    assert isinstance(result, type)
    assert result is type(list[int])  # type: ignore[comparison-overlap]

    result = parser.parse("typing.List[int]")
    assert isinstance(result, type)
    assert result is type(list[int])  # type: ignore[comparison-overlap]

    result = parser.parse("collections.abc.List[int]")
    assert isinstance(result, type)
    assert result is type(list[int])  # type: ignore[comparison-overlap]


def test_parse_set():
    """Test parsing set types."""
    parser = TypeStrParser(create_mock_type_system())
    result = parser.parse("Set[int]")
    assert isinstance(result, type)
    assert result is type(set[int])  # type: ignore[comparison-overlap]

    result = parser.parse("set[int]")
    assert isinstance(result, type)
    assert result is type(set[int])  # type: ignore[comparison-overlap]

    result = parser.parse("typing.Set[int]")
    assert isinstance(result, type)
    assert result is type(set[int])  # type: ignore[comparison-overlap]

    result = parser.parse("collections.abc.Set[int]")
    assert isinstance(result, type)
    assert result is type(set[int])  # type: ignore[comparison-overlap]


def test_parse_simple_types():
    """Test parsing simple types."""
    mock_type_system = create_mock_type_system()
    parser = TypeStrParser(mock_type_system)
    result = parser.parse("int")
    assert result is int


def create_mock_type_system() -> Mock:
    """Create a mock type system with predefined types int and str."""
    mock_type_system = Mock()

    # Create mock TypeInfo for int
    int_type = Mock()
    int_type.qualname = "int"
    int_type.name = "int"
    int_type.full_name = "builtins.int"
    int_type.raw_type = int

    # Create mock TypeInfo for str
    str_type = Mock()
    str_type.qualname = "str"
    str_type.name = "str"
    str_type.full_name = "builtins.str"
    str_type.raw_type = str

    mock_type_system.get_all_types.return_value = [int_type, str_type]
    return mock_type_system
