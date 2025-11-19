#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2024 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
"""Tests for TypeEvalPy integration with Pynguin's type inference."""

import importlib
import json
import tempfile
import typing
from logging import Logger
from pathlib import Path
from unittest.mock import MagicMock

import pynguin.configuration as config
import pynguin.ga.generationalgorithmfactory as gaf
from pynguin.analyses.module import generate_test_cluster
from pynguin.analyses.type_inference import TypeEvalPyInference
from pynguin.analyses.typesystem import (
    TypeSystem,
)
from pynguin.instrumentation.machinery import install_import_hook
from pynguin.instrumentation.tracer import SubjectProperties
from pynguin.testcase.execution import TestCaseExecutor
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
            file="test_typeevalpy_integration.py",
            line_number=1,
            type=["int"],
            function="foo",
            parameter="bar",
        ),
        TypeEvalPySchemaElement(
            file="test_typeevalpy_integration.py",
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
            file="test_typeevalpy_integration.py",
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


def test_parse_json():
    """Test complete JSON parsing and integration."""
    # Create a temporary JSON file
    test_data = [
        {
            "file": "test_typeevalpy_integration.py",
            "line_number": 1,
            "type": ["int"],
            "function": "foo",
            "parameter": "bar",
        },
        {
            "file": "test_typeevalpy_integration.py",
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


def test_type_conversion():
    """Test type conversion."""
    elements = [
        TypeEvalPySchemaElement(
            file="test_typeevalpy_integration.py",
            line_number=1,
            type=["unknown.Type"],
            function="foo",
            parameter="x",
        ),
        TypeEvalPySchemaElement(
            file="test_typeevalpy_integration.py",
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


def test_integrate(subject_properties: SubjectProperties):
    module_name = "tests.resources.typeevalpy.dummy"
    typeevalpy_resources = Path(__file__).parent.parent / "resources" / "typeevalpy"
    config.configuration.type_inference.typeevalpy_json_path = str(
        typeevalpy_resources / "dummy_gt.json"
    )
    algorithm = config.Algorithm.DYNAMOSA
    config.configuration.algorithm = algorithm
    config.configuration.stopping.maximum_iterations = 2
    config.configuration.module_name = module_name
    config.configuration.search_algorithm.min_initial_tests = 1
    config.configuration.search_algorithm.max_initial_tests = 1
    config.configuration.search_algorithm.population = 2
    config.configuration.test_creation.none_weight = 1
    config.configuration.test_creation.any_weight = 1
    logger = MagicMock(Logger)
    with install_import_hook(module_name, subject_properties):
        # Need to force reload in order to apply instrumentation.
        with subject_properties.instrumentation_tracer:
            module = importlib.import_module(module_name)
            importlib.reload(module)

        executor = TestCaseExecutor(subject_properties)
        cluster = generate_test_cluster(
            module_name, type_inference_strategy=config.TypeInferenceStrategy.TYPEEVALPY
        )
        search_algorithm = gaf.TestSuiteGenerationAlgorithmFactory(
            executor, cluster
        ).get_search_algorithm()
        search_algorithm._logger = logger
        test_cases = search_algorithm.generate_tests()
        assert test_cases.size() >= 0
