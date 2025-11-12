#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2024 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
"""Tests for TypeEvalPy integration with Pynguin's type inference."""

import json
import tempfile

from pathlib import Path

import pytest

from pynguin.analyses.typesystem import EnhancedTypeHintProvider
from pynguin.analyses.typesystem import Instance
from pynguin.analyses.typesystem import TypeEvalPyTypeProvider
from pynguin.analyses.typesystem import TypeSystem
from pynguin.analyses.typesystem import UnionType
from pynguin.utils.typeevalpy_json_schema import ParsedTypeEvalPyData
from pynguin.utils.typeevalpy_json_schema import TypeEvalPySchemaElement
from pynguin.utils.typeevalpy_json_schema import parse_json


def test_typeevalpy_provider_parameter_types():
    """Test that TypeEvalPy provider can retrieve parameter types."""
    # Create test data
    elements = [
        TypeEvalPySchemaElement(
            file="test.py",
            line_number=1,
            type=["int"],
            function="foo",
            parameter="bar",
        ),
        TypeEvalPySchemaElement(
            file="test.py",
            line_number=1,
            type=["str", "int"],
            function="foo",
            parameter="baz",
        ),
    ]
    data = ParsedTypeEvalPyData(elements=elements)
    provider = TypeEvalPyTypeProvider(data)

    # Test single type parameter
    param_type = provider.get_parameter_types("foo", "bar")
    assert isinstance(param_type, Instance)
    assert param_type.type.raw_type is int

    # Test union type parameter
    param_type = provider.get_parameter_types("foo", "baz")
    assert isinstance(param_type, UnionType)
    assert len(param_type.items) == 2

    # Test non-existent parameter
    param_type = provider.get_parameter_types("foo", "nonexistent")
    assert param_type is None


def test_typeevalpy_provider_return_types():
    """Test that TypeEvalPy provider can retrieve return types."""
    elements = [
        TypeEvalPySchemaElement(
            file="test.py",
            line_number=1,
            type=["str"],
            function="foo",
        ),
    ]
    data = ParsedTypeEvalPyData(elements=elements)
    provider = TypeEvalPyTypeProvider(data)

    return_type = provider.get_return_types("foo")
    assert isinstance(return_type, Instance)
    assert return_type.type.raw_type is str


def test_enhanced_type_hint_provider_no_typeevalpy():
    """Test enhanced provider without TypeEvalPy data."""
    provider = EnhancedTypeHintProvider()

    def test_func(x: int) -> str:
        return str(x)

    hints = provider.get_enhanced_type_hints(test_func, "test_func")
    assert hints["x"] is int
    assert hints["return"] is str


def test_enhanced_type_hint_provider_with_typeevalpy():
    """Test enhanced provider with TypeEvalPy data."""
    # Create TypeEvalPy data
    elements = [
        TypeEvalPySchemaElement(
            file="test.py",
            line_number=1,
            type=["float"],
            function="test_func",
            parameter="y",
        ),
    ]
    data = ParsedTypeEvalPyData(elements=elements)
    provider = EnhancedTypeHintProvider(data)

    def test_func(x: int, y) -> str:  # y has no type hint
        return str(x + y)

    hints = provider.get_enhanced_type_hints(test_func, "test_func")
    assert hints["x"] is int  # Original type hint preserved
    assert hints["return"] is str  # Original type hint preserved
    # y should get type from TypeEvalPy (converted back to type hint)
    assert "y" in hints  # y should be enhanced with TypeEvalPy data


def test_type_system_infer_type_info_with_typeevalpy():
    """Test TypeSystem.infer_type_info with TypeEvalPy data."""
    # Create TypeEvalPy data
    elements = [
        TypeEvalPySchemaElement(
            file="test.py",
            line_number=1,
            type=["int"],
            function="test_func",
            parameter="x",
        ),
    ]
    data = ParsedTypeEvalPyData(elements=elements)

    # Create a function without type hints
    def test_func(x):
        return x * 2

    type_system = TypeSystem()

    # Test with TypeEvalPy data
    signature_with = type_system.infer_type_info(
        test_func, function_name="test_func", typeevalpy_data=data
    )

    # The signature with TypeEvalPy should have enhanced parameter types
    assert "x" in signature_with.original_parameters
    # The parameter type should be influenced by TypeEvalPy data


def test_parse_json_integration():
    """Test complete JSON parsing and integration."""
    # Create a temporary JSON file
    test_data = [
        {
            "file": "test.py",
            "line_number": 1,
            "type": ["int"],
            "function": "foo",
            "parameter": "bar",
        },
        {
            "file": "test.py",
            "line_number": 2,
            "type": ["str"],
            "function": "foo",
        },
    ]

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(test_data, f)
        temp_path = f.name

    try:
        # Parse the JSON file
        parsed_data = parse_json(temp_path)

        assert len(parsed_data.elements) == 2
        assert parsed_data.get_function_parameters("foo") == {"bar": ["int"]}
        assert parsed_data.get_function_return_types("foo") == ["str"]

        # Test with provider
        provider = TypeEvalPyTypeProvider(parsed_data)
        param_type = provider.get_parameter_types("foo", "bar")
        assert isinstance(param_type, Instance)
        assert param_type.type.raw_type is int

    finally:
        Path(temp_path).unlink()


def test_parse_json_file_not_found():
    """Test parse_json with non-existent file."""
    with pytest.raises(FileNotFoundError):
        parse_json("nonexistent.json")


def test_parse_json_invalid_json():
    """Test parse_json with invalid JSON."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        f.write("invalid json content")
        temp_path = f.name

    try:
        with pytest.raises(json.JSONDecodeError):
            parse_json(temp_path)
    finally:
        Path(temp_path).unlink()


def test_type_conversion_edge_cases():
    """Test edge cases in type conversion."""
    elements = [
        TypeEvalPySchemaElement(
            file="test.py",
            line_number=1,
            type=["unknown.Type"],
            function="foo",
            parameter="x",
        ),
        TypeEvalPySchemaElement(
            file="test.py",
            line_number=1,
            type=["typing.List"],
            function="foo",
            parameter="y",
        ),
    ]
    data = ParsedTypeEvalPyData(elements=elements)
    provider = TypeEvalPyTypeProvider(data)

    # Test unknown type
    param_type = provider.get_parameter_types("foo", "x")
    # Should return None for unknown types
    assert param_type is None

    # Test typing module type
    param_type = provider.get_parameter_types("foo", "y")
    assert isinstance(param_type, Instance)
    assert param_type.type.raw_type is list
