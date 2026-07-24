#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Tests for the temperature=0 fallback in the OpenAI client."""
# ruff: noqa: PLC2701  # intentionally exercising private client internals

from unittest.mock import MagicMock

import pytest

import pynguin.configuration as config
from pynguin.large_language_model.client import (
    _TEMPERATURE_FALLBACK,
    OpenAIClient,
    _is_temperature_unsupported_error,
)
from pynguin.large_language_model.request import RenderedRequest


class _FakeSecret:
    """Minimal stand-in for a pydantic SecretStr."""

    def get_secret_value(self) -> str:
        return "test-key"


def _make_client(monkeypatch) -> OpenAIClient:
    monkeypatch.setattr("pynguin.large_language_model.client.get_llm_url", lambda: None)
    monkeypatch.setattr("pynguin.large_language_model.client.openai.OpenAI", MagicMock)
    return OpenAIClient(api_key=_FakeSecret(), model="test-model")


def _make_response(content: str) -> MagicMock:
    response = MagicMock()
    response.choices[0].message.content = content
    response.usage.prompt_tokens = 1
    response.usage.completion_tokens = 1
    return response


def _request(temperature: float) -> RenderedRequest:
    return RenderedRequest(
        messages=[{"role": "user", "content": "hi"}],
        model="test-model",
        temperature=temperature,
    )


@pytest.mark.parametrize(
    "message,expected",
    [
        ("400: 'temperature' does not support 0.0", True),
        ("Unsupported value: temperature must be >= 0.1", True),
        ("some unrelated rate limit error", False),
    ],
)
def test_is_temperature_unsupported_error(message, expected):
    assert _is_temperature_unsupported_error(Exception(message)) is expected


def test_temperature_zero_falls_back_to_positive(monkeypatch, caplog):
    monkeypatch.setattr(config.configuration.large_language_model, "enable_response_caching", False)
    client = _make_client(monkeypatch)

    good_response = _make_response("```python\nx = 1\n```")
    create = MagicMock(
        side_effect=[Exception("400: 'temperature' does not support 0.0"), good_response]
    )
    client._client.chat.completions.create = create

    with caplog.at_level("WARNING"):
        result = client.send(_request(0.0))

    assert result == "```python\nx = 1\n```"
    # Two attempts: the first with 0, the retry with the fallback temperature.
    assert create.call_count == 2
    assert create.call_args_list[0].kwargs["temperature"] == 0.0
    assert create.call_args_list[1].kwargs["temperature"] == _TEMPERATURE_FALLBACK
    assert any("temperature=0" in record.message for record in caplog.records)
    # A single logical request is counted regardless of the fallback retry.
    assert client.get_usage()["calls"] == 1


def test_temperature_zero_rejection_is_remembered_across_requests(monkeypatch, caplog):
    monkeypatch.setattr(config.configuration.large_language_model, "enable_response_caching", False)
    client = _make_client(monkeypatch)

    # First request: 0 fails, retry at the fallback succeeds.
    first = MagicMock(
        side_effect=[Exception("400: 'temperature' does not support 0.0"), _make_response("a")]
    )
    client._client.chat.completions.create = first
    with caplog.at_level("WARNING"):
        client.send(_request(0.0))
    assert first.call_count == 2
    assert client._temperature_zero_rejected is True
    warnings_after_first = sum(1 for r in caplog.records if "temperature=0" in r.message)

    # Second request also asks for 0, but the client now skips the doomed attempt:
    # a single call, made directly at the fallback temperature, and no new warning.
    second = MagicMock(return_value=_make_response("b"))
    client._client.chat.completions.create = second
    with caplog.at_level("WARNING"):
        client.send(_request(0.0))
    assert second.call_count == 1
    assert second.call_args_list[0].kwargs["temperature"] == _TEMPERATURE_FALLBACK
    assert sum(1 for r in caplog.records if "temperature=0" in r.message) == warnings_after_first


def test_nonzero_temperature_is_not_retried_for_temperature_error(monkeypatch):
    monkeypatch.setattr(config.configuration.large_language_model, "enable_response_caching", False)
    monkeypatch.setattr(config.configuration.large_language_model, "max_retries", 1)
    client = _make_client(monkeypatch)

    create = MagicMock(side_effect=Exception("400: 'temperature' does not support 0.5"))
    client._client.chat.completions.create = create

    # A non-zero temperature is never eligible for the fallback, so the error surfaces.
    with pytest.raises(Exception, match="temperature"):
        client.send(_request(0.5))
    assert create.call_count == 1
