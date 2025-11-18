#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2024 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
"""Tests for TypeEvalPy integration with Pynguin's type inference."""

import json
import tempfile
import typing
from pathlib import Path

import pytest

from pynguin.analyses.type_inference import TypeEvalPyInference
from pynguin.analyses.typesystem import (
    TypeSystem,
)
from pynguin.utils.typeevalpy_json_schema import (
    ParsedTypeEvalPyData,
    TypeEvalPySchemaElement,
    parse_json,
)


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
    provider = TypeEvalPyInference(typeevalpy_data=data)

    # Define a matching function and get hints
    def foo(bar, baz):
        pass

    hints = provider.provide(foo)

    # Test single type parameter
    assert "bar" in hints
    assert hints["bar"] is int

    baz_hint = hints.get("baz")
    assert baz_hint is not None
    assert set(typing.get_args(baz_hint)) == {str, int}

    # Test non-existent parameter
    assert "nonexistent" not in hints


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
    provider = TypeEvalPyInference(typeevalpy_data=data)

    def foo():
        return ""

    hints = provider.provide(foo)
    assert "return" in hints
    assert hints["return"] is str


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

    provider = TypeEvalPyInference(typeevalpy_data=data)
    signature_with = type_system.infer_type_info(test_func, type_inference_provider=provider)

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
        provider = TypeEvalPyInference(typeevalpy_data=parsed_data)

        def foo(bar):  # noqa: ARG001
            return None

        hints = provider.provide(foo)
        assert "bar" in hints
        assert hints["bar"] is int

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
    provider = TypeEvalPyInference(typeevalpy_data=data)

    def foo(x, y):  # noqa: ARG001
        return None

    hints = provider.provide(foo)

    # Test unknown type: should not be present
    assert "x" not in hints

    # Test typing module type
    assert "y" in hints
    assert hints["y"] is list
