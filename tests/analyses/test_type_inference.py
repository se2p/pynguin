#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
"""Tests for type inference module."""

import ast
import math
import operator
from typing import Any
from unittest.mock import Mock, patch

import typeshed_client

from pynguin.analyses.type_inference import (
    HintInference,
    LLMInference,
    NoInference,
    TypeshedInference,
)
from pynguin.analyses.typesystem import AnyType, TypeSystem
from pynguin.utils.llm import LLMProvider


def _function_name_info(source: str) -> typeshed_client.NameInfo:
    """Builds a NameInfo for a top-level function from a stub source snippet."""
    function_def = ast.parse(source).body[0]
    return typeshed_client.NameInfo(
        name=function_def.name, is_exported=True, ast=function_def, child_nodes=None
    )


def test_no_inference():
    """Test that NoInference always returns empty dict."""
    provider = NoInference()
    assert provider.provide(lambda x: x) == {}
    assert provider.get_metrics() == {
        "failed_inferences": 0,
        "successful_inferences": 0,
        "sent_requests": 0,
        "total_setup_time": 0,
    }


def test_hint_inference_with_valid_hints():
    """Test HintInference with valid type hints."""

    def example_func(x: int, y: str) -> bool:
        return bool(x) and bool(y)

    provider = HintInference()
    hints = provider.provide(example_func)
    assert hints == {"x": int, "y": str, "return": bool}


def test_hint_inference_with_no_hints():
    """Test HintInference with function having no type hints."""
    provider = HintInference()
    hints = provider.provide(operator.add)
    assert hints == {}


def test_llm_inference_basic():
    """Test basic functionality of LLMInference."""

    def example_func(x: int, y: str) -> None:
        pass

    mock_type_info_str = Mock()
    mock_type_info_str.name.return_value = "str"
    mock_type_info_str.qualname.return_value = "builtins.str"

    mock_type_info_int = Mock()
    mock_type_info_int.name.return_value = "int"
    mock_type_info_int.qualname.return_value = "builtins.int"

    mock_type_system = Mock()
    mock_type_system.get_all_types.return_value = [mock_type_info_str, mock_type_info_int]
    mock_type_system.get_subclasses.return_value = []

    with patch("pynguin.analyses.type_inference.OpenAIClient") as mock_openai:
        mock_openai.return_value.send.return_value = """{"x": "int", "y": "str"}"""

        provider = LLMInference(
            [example_func],
            LLMProvider.OPENAI,
            mock_type_system,
        )

        result = provider.provide(example_func)
        assert "x" in result
        assert "y" in result


def test_llm_inference_invalid_json():
    """Test LLMInference with invalid JSON response."""

    def example_func(x: Any, y: Any) -> None:
        pass

    mock_type_system = Mock()
    mock_type_system.get_all_types.return_value = []
    mock_type_system.get_subclasses.return_value = []

    with patch("pynguin.analyses.type_inference.OpenAIClient") as mock_openai:
        mock_openai.return_value.send.return_value = "invalid json"

        provider = LLMInference(
            [example_func],
            LLMProvider.OPENAI,
            mock_type_system,
        )

        result = provider.provide(example_func)
        assert isinstance(result, dict)
        metrics = provider.get_metrics()
        assert metrics["failed_inferences"] > 0


def test_llm_inference_empty_response():
    """Test LLMInference with empty response."""

    def example_func(x: Any, y: Any) -> None:
        pass

    mock_type_system = Mock()
    mock_type_system.get_all_types.return_value = []
    mock_type_system.get_subclasses.return_value = []

    with patch("pynguin.analyses.type_inference.OpenAIClient") as mock_openai:
        mock_openai.return_value.send.return_value = ""

        provider = LLMInference(
            [example_func],
            LLMProvider.OPENAI,
            mock_type_system,
        )

        result = provider.provide(example_func)
        assert isinstance(result, dict)
        assert all(isinstance(v, type) for v in result.values())


def test_typeshed_inference_fills_hint_gap():
    """TypeshedInference should fill in parameters missing from runtime hints."""

    def foo(x, y):
        pass

    foo.__module__ = "fakemod_fill_gap"
    foo.__qualname__ = "foo"
    stub_info = _function_name_info("def foo(x: int, y: str) -> bool: ...")

    provider = TypeshedInference(TypeSystem())
    with patch(
        "pynguin.analyses.type_inference.typeshed_client.get_stub_names",
        side_effect=lambda name: {"foo": stub_info} if name == "fakemod_fill_gap" else None,
    ):
        result = provider.provide(foo)

    assert result == {"x": int, "y": str, "return": bool}


def test_typeshed_inference_prefers_runtime_hints():
    """Runtime type hints must take precedence over typeshed stub information."""

    def foo(x: float, y):
        pass

    foo.__module__ = "fakemod_prefers_hints"
    foo.__qualname__ = "foo"
    stub_info = _function_name_info("def foo(x: int, y: str) -> bool: ...")

    provider = TypeshedInference(TypeSystem())
    with patch(
        "pynguin.analyses.type_inference.typeshed_client.get_stub_names",
        side_effect=lambda name: {"foo": stub_info} if name == "fakemod_prefers_hints" else None,
    ):
        result = provider.provide(foo)

    assert result["x"] is float
    assert result["y"] is str
    assert result["return"] is bool


def test_typeshed_inference_unresolvable_type_is_skipped():
    """Unresolvable stub type strings must be skipped, not raise or produce garbage."""

    def foo(x):
        pass

    foo.__module__ = "fakemod_unresolvable"
    foo.__qualname__ = "foo"
    stub_info = _function_name_info("def foo(x: SomeUnknownProtocol) -> None: ...")

    provider = TypeshedInference(TypeSystem())
    with patch(
        "pynguin.analyses.type_inference.typeshed_client.get_stub_names",
        side_effect=lambda name: {"foo": stub_info} if name == "fakemod_unresolvable" else None,
    ):
        result = provider.provide(foo)

    assert "x" not in result
    assert result["return"] is type(None)
    metrics = provider.get_metrics()
    assert metrics["failed_inferences"] == 1
    assert metrics["successful_inferences"] == 1


def test_typeshed_inference_overload_uses_first_definition():
    """Overloaded stub functions should resolve using the first definition."""

    def foo(x):
        pass

    foo.__module__ = "fakemod_overload"
    foo.__qualname__ = "foo"
    definitions = [
        ast.parse("def foo(x: int) -> int: ...").body[0],
        ast.parse("def foo(x: str) -> str: ...").body[0],
    ]
    overloaded_info = typeshed_client.NameInfo(
        name="foo",
        is_exported=True,
        ast=typeshed_client.OverloadedName(definitions=definitions),
        child_nodes=None,
    )

    provider = TypeshedInference(TypeSystem())
    with patch(
        "pynguin.analyses.type_inference.typeshed_client.get_stub_names",
        side_effect=lambda name: {"foo": overloaded_info} if name == "fakemod_overload" else None,
    ):
        result = provider.provide(foo)

    assert result == {"x": int, "return": int}


def test_typeshed_inference_no_stub_available():
    """When no stub is found, the result must fall back to runtime hints only."""

    def foo(x: int):
        pass

    foo.__module__ = "totally_nonexistent_module_xyz"

    provider = TypeshedInference(TypeSystem())
    with patch(
        "pynguin.analyses.type_inference.typeshed_client.get_stub_names",
        return_value=None,
    ):
        result = provider.provide(foo)

    assert result == {"x": int}


def test_typeshed_inference_skips_nested_functions():
    """Callables defined inside another function must not trigger stub lookups."""

    def outer():
        def inner(x):
            pass

        return inner

    fn = outer()
    fn.__module__ = "fakemod_nested"

    provider = TypeshedInference(TypeSystem())
    with patch(
        "pynguin.analyses.type_inference.typeshed_client.get_stub_names"
    ) as mock_get_stub_names:
        result = provider.provide(fn)

    mock_get_stub_names.assert_not_called()
    assert result == {}


def test_typeshed_inference_class_init_base_class_fallback():
    """A class without its own ``__init__`` must inherit types from its base."""
    module_source = """
class Base:
    def __init__(self, z: int) -> None: ...

class Sub(Base):
    pass
"""
    tree = ast.parse(module_source)
    base_class_def, sub_class_def = tree.body
    base_init_fn = base_class_def.body[0]
    names = {
        "Base": typeshed_client.NameInfo(
            name="Base",
            is_exported=True,
            ast=base_class_def,
            child_nodes={
                "__init__": typeshed_client.NameInfo(
                    name="__init__", is_exported=True, ast=base_init_fn, child_nodes=None
                )
            },
        ),
        "Sub": typeshed_client.NameInfo(
            name="Sub", is_exported=True, ast=sub_class_def, child_nodes={}
        ),
    }

    def init_method(self, z):
        pass

    init_method.__module__ = "fakemod_base_fallback"
    init_method.__qualname__ = "Sub.__init__"

    provider = TypeshedInference(TypeSystem())
    with patch(
        "pynguin.analyses.type_inference.typeshed_client.get_stub_names",
        side_effect=lambda name: names if name == "fakemod_base_fallback" else None,
    ):
        result = provider.provide(init_method)

    assert result == {"z": int, "return": type(None)}


def test_typeshed_inference_real_stdlib_function():
    """End-to-end sanity check against the real typeshed data for a stable stdlib API."""
    provider = TypeshedInference(TypeSystem())
    result = provider.provide(math.sqrt)
    assert result.get("return") is float


def test_typeshed_strategy_improves_on_type_hints_via_type_system():
    """The TYPESHED strategy must recover more type info than TYPE_HINTS alone.

    Exercises the real integration point (``TypeSystem.infer_type_info``), not
    just the provider in isolation: ``math.sqrt`` has no runtime annotations at
    all, so ``HintInference`` cannot supply a return type, while
    ``TypeshedInference`` recovers it from typeshed's stub data.
    """
    type_system = TypeSystem()

    hint_only = type_system.infer_type_info(math.sqrt, type_inference_provider=HintInference())
    assert isinstance(hint_only.return_type, AnyType)

    via_typeshed = type_system.infer_type_info(
        math.sqrt, type_inference_provider=TypeshedInference(type_system)
    )
    assert via_typeshed.return_type == type_system.convert_type_hint(float)
    assert not isinstance(via_typeshed.return_type, AnyType)
