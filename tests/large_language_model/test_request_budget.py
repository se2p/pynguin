#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Tests for the per-request time budget and retry layering in the OpenAI client."""
# ruff: noqa: PLC2701  # intentionally exercising private client internals

from unittest.mock import MagicMock

import pytest

import pynguin.configuration as config
from pynguin.large_language_model.client import OpenAIClient, _retry_fits_in_budget
from pynguin.large_language_model.request import RenderedRequest


class _FakeSecret:
    """Minimal stand-in for a pydantic SecretStr."""

    def get_secret_value(self) -> str:
        return "test-key"


class _FakeTimeoutError(Exception):
    """Stands in for ``openai.APITimeoutError``."""


def _make_client(monkeypatch, openai_factory=MagicMock) -> OpenAIClient:
    monkeypatch.setattr("pynguin.large_language_model.client.get_llm_url", lambda: None)
    monkeypatch.setattr("pynguin.large_language_model.client.openai.OpenAI", openai_factory)
    client = OpenAIClient(api_key=_FakeSecret(), model="test-model")
    client._timeout_errors = (_FakeTimeoutError,)
    client._rate_limit_errors = ()
    client._api_errors = ()
    return client


def _request() -> RenderedRequest:
    return RenderedRequest(
        messages=[{"role": "user", "content": "hi"}],
        model="test-model",
        temperature=0.2,
    )


def test_sdk_internal_retries_are_disabled(monkeypatch):
    """The SDK must not retry underneath us, or the two layers multiply."""
    recorded: dict[str, object] = {}

    def _factory(**kwargs):
        recorded.update(kwargs)
        return MagicMock()

    _make_client(monkeypatch, openai_factory=_factory)

    assert recorded["max_retries"] == 0


@pytest.mark.parametrize(
    "budget,elapsed,wait,timeout,expected",
    [
        # Disabled budget always admits another attempt.
        (0.0, 10_000.0, 5.0, 30.0, True),
        (-1.0, 10_000.0, 5.0, 30.0, True),
        # Backoff plus a full attempt still fits.
        (300.0, 100.0, 5.0, 30.0, True),
        # Exactly fits.
        (300.0, 265.0, 5.0, 30.0, True),
        # One second too long.
        (300.0, 266.0, 5.0, 30.0, False),
        # An unbounded attempt is admitted only while budget remains.
        (300.0, 100.0, 5.0, None, True),
        (300.0, 299.0, 5.0, None, False),
    ],
)
def test_retry_fits_in_budget(budget, elapsed, wait, timeout, expected):
    assert (
        _retry_fits_in_budget(budget=budget, elapsed=elapsed, wait=wait, timeout=timeout)
        is expected
    )


def test_send_stops_retrying_once_the_budget_cannot_fit_another_attempt(monkeypatch):
    monkeypatch.setattr(config.configuration.large_language_model, "enable_response_caching", False)
    monkeypatch.setattr(config.configuration.large_language_model, "max_retries", 8)
    monkeypatch.setattr(config.configuration.large_language_model, "request_timeout", 30.0)
    # Room for the first attempt only: any retry needs backoff + another 30s.
    monkeypatch.setattr(config.configuration.large_language_model, "max_request_time", 30.0)
    monkeypatch.setattr("pynguin.large_language_model.client.time.sleep", lambda _s: None)

    client = _make_client(monkeypatch)
    create = MagicMock(side_effect=_FakeTimeoutError("Request timed out."))
    client._client.chat.completions.create = create

    with pytest.raises(_FakeTimeoutError):
        client.send(_request())

    assert create.call_count == 1, "the budget must prevent a second attempt"
    assert client.get_usage()["retries"] == 0


def test_send_exhausts_max_retries_when_the_budget_is_disabled(monkeypatch):
    monkeypatch.setattr(config.configuration.large_language_model, "enable_response_caching", False)
    monkeypatch.setattr(config.configuration.large_language_model, "max_retries", 3)
    monkeypatch.setattr(config.configuration.large_language_model, "request_timeout", 30.0)
    monkeypatch.setattr(config.configuration.large_language_model, "max_request_time", 0.0)
    monkeypatch.setattr("pynguin.large_language_model.client.time.sleep", lambda _s: None)

    client = _make_client(monkeypatch)
    create = MagicMock(side_effect=_FakeTimeoutError("Request timed out."))
    client._client.chat.completions.create = create

    with pytest.raises(_FakeTimeoutError):
        client.send(_request())

    assert create.call_count == 3


def test_send_uses_the_explicit_timeout_override(monkeypatch):
    monkeypatch.setattr(config.configuration.large_language_model, "enable_response_caching", False)
    monkeypatch.setattr(config.configuration.large_language_model, "request_timeout", 30.0)

    client = _make_client(monkeypatch)
    response = MagicMock()
    response.choices[0].message.content = "ok"
    response.usage.prompt_tokens = 1
    response.usage.completion_tokens = 1
    create = MagicMock(return_value=response)
    client._client.chat.completions.create = create

    client.send(_request(), timeout=180.0)

    assert create.call_args.kwargs["timeout"] == 180.0


def test_send_falls_back_to_the_configured_timeout(monkeypatch):
    monkeypatch.setattr(config.configuration.large_language_model, "enable_response_caching", False)
    monkeypatch.setattr(config.configuration.large_language_model, "request_timeout", 25.0)

    client = _make_client(monkeypatch)
    response = MagicMock()
    response.choices[0].message.content = "ok"
    response.usage.prompt_tokens = 1
    response.usage.completion_tokens = 1
    client._client.chat.completions.create = MagicMock(return_value=response)

    client.send(_request())

    assert client._client.chat.completions.create.call_args.kwargs["timeout"] == 25.0
