#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
"""Tests for type inference module."""

import operator
from typing import Any
from unittest.mock import Mock, patch

from pynguin.analyses.type_inference import HintInference, LLMInference, NoInference
from pynguin.utils.llm import LLMProvider


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

    with patch("pynguin.analyses.type_inference.OpenAI") as mock_openai:
        mock_openai.return_value.chat.return_value = """{"x": "int", "y": "str"}"""

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

    with patch("pynguin.analyses.type_inference.OpenAI") as mock_openai:
        mock_openai.return_value.chat.return_value = "invalid json"

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

    with patch("pynguin.analyses.type_inference.OpenAI") as mock_openai:
        mock_openai.return_value.chat.return_value = ""

        provider = LLMInference(
            [example_func],
            LLMProvider.OPENAI,
            mock_type_system,
        )

        result = provider.provide(example_func)
        assert isinstance(result, dict)
        assert all(isinstance(v, type) for v in result.values())
