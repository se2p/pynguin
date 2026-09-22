# This file is part of Pynguin.
#
# SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
# SPDX-License-Identifier: MIT
#
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pynguin.configuration as config
from pynguin.large_language_model.client import OpenAIClient
from pynguin.large_language_model.request import RenderedRequest


class _FakeSecret:
    def get_secret_value(self) -> str:
        return "test-key"


def _make_client(monkeypatch) -> OpenAIClient:
    monkeypatch.setattr("pynguin.large_language_model.client.get_llm_url", lambda: None)
    monkeypatch.setattr("pynguin.large_language_model.client.openai.OpenAI", MagicMock)
    monkeypatch.setattr("pynguin.large_language_model.client.openai.AsyncOpenAI", MagicMock)
    monkeypatch.setattr(config.configuration.large_language_model, "enable_response_caching", False)
    return OpenAIClient(api_key=_FakeSecret(), model="test-model")


def _make_response(content: str, prompt_tokens: int = 10, completion_tokens: int = 5) -> MagicMock:
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message.content = content
    response.usage = MagicMock()
    response.usage.prompt_tokens = prompt_tokens
    response.usage.completion_tokens = completion_tokens
    return response


def _request(content: str = "hi", temperature: float = 0.5) -> RenderedRequest:
    return RenderedRequest(
        messages=[{"role": "user", "content": content}],
        model="test-model",
        temperature=temperature,
    )


def test_send_async_success(monkeypatch):
    client = _make_client(monkeypatch)
    mock_async_create = AsyncMock(return_value=_make_response("```python\nx = 42\n```"))
    client._async_client = MagicMock()
    client._async_client.chat.completions.create = mock_async_create

    result = asyncio.run(client.send_async(_request()))

    assert result == "```python\nx = 42\n```"
    mock_async_create.assert_awaited_once()
    usage = client.get_usage()
    assert usage["calls"] == 1
    assert usage["input_tokens"] == 10
    assert usage["output_tokens"] == 5
    assert usage["calls_with_no_python_code"] == 0


def test_send_async_codeless_response(monkeypatch):
    client = _make_client(monkeypatch)
    mock_async_create = AsyncMock(return_value=_make_response("Here is plain text without code"))
    client._async_client = MagicMock()
    client._async_client.chat.completions.create = mock_async_create

    result = asyncio.run(client.send_async(_request()))

    assert result == "Here is plain text without code"
    usage = client.get_usage()
    assert usage["calls_with_no_python_code"] == 1


def test_send_async_caching(monkeypatch):
    client = _make_client(monkeypatch)
    monkeypatch.setattr(config.configuration.large_language_model, "enable_response_caching", True)
    req = _request()
    client.cache.set(req, "cached response")

    mock_async_create = AsyncMock()
    client._async_client = MagicMock()
    client._async_client.chat.completions.create = mock_async_create

    result = asyncio.run(client.send_async(req))

    assert result == "cached response"
    mock_async_create.assert_not_called()


def test_send_async_temperature_zero_fallback(monkeypatch):
    client = _make_client(monkeypatch)
    req = _request(temperature=0.0)

    # First attempt raises unsupported temperature error, second succeeds
    fail_exc = Exception("Unsupported temperature parameter value")
    success_resp = _make_response("```python\nassert True\n```")

    mock_async_create = AsyncMock(side_effect=[fail_exc, success_resp])
    client._async_client = MagicMock()
    client._async_client.chat.completions.create = mock_async_create

    result = asyncio.run(client.send_async(req))

    assert result == "```python\nassert True\n```"
    assert mock_async_create.await_count == 2
    assert client._temperature_zero_rejected is True


def test_send_batch_async_concurrency(monkeypatch):
    client = _make_client(monkeypatch)
    max_concurrency = 3
    current_concurrency = 0
    peak_concurrency = 0

    async def fake_create(**kwargs):
        nonlocal current_concurrency, peak_concurrency
        current_concurrency += 1
        peak_concurrency = max(peak_concurrency, current_concurrency)
        await asyncio.sleep(0.05)
        current_concurrency -= 1
        return _make_response(f"resp for {kwargs['messages'][0]['content']}")

    client._async_client = MagicMock()
    client._async_client.chat.completions.create = AsyncMock(side_effect=fake_create)

    requests = [_request(f"prompt_{i}") for i in range(10)]
    results = asyncio.run(client.send_batch_async(requests, max_concurrency=max_concurrency))

    assert len(results) == 10
    for i, res in enumerate(results):
        assert res == f"resp for prompt_{i}"
    assert peak_concurrency <= max_concurrency
    assert peak_concurrency > 1


def test_send_batch_sync(monkeypatch):
    client = _make_client(monkeypatch)

    async def fake_create(**kwargs):
        await asyncio.sleep(0)
        return _make_response(f"sync resp {kwargs['messages'][0]['content']}")

    client._async_client = MagicMock()
    client._async_client.chat.completions.create = AsyncMock(side_effect=fake_create)

    requests = [_request(f"req_{i}") for i in range(4)]
    results = client.send_batch(requests, max_concurrency=2)

    assert len(results) == 4
    for i, res in enumerate(results):
        assert res == f"sync resp req_{i}"


def test_cancel_all_closes_clients_and_aborts_subsequent_requests(monkeypatch):
    client = _make_client(monkeypatch)
    _ = client.async_client
    async_mock_close = AsyncMock()
    client._async_client.close = async_mock_close

    assert client._is_cancelled is False

    client.cancel_all()

    assert client._is_cancelled is True
    client._client.close.assert_called_once()
    async_mock_close.assert_called_once()

    req = _request("test")
    assert client.send(req) is None
    assert asyncio.run(client.send_async(req)) is None


def test_cancel_all_during_in_flight_send(monkeypatch):
    client = _make_client(monkeypatch)

    def fake_create(**_kwargs):
        client.cancel_all()
        raise RuntimeError("Socket closed")

    client._client.chat.completions.create = MagicMock(side_effect=fake_create)
    req = _request("test")
    result = client.send(req)
    assert result is None
