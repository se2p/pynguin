#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Tests for the sampling seed the OpenAI client sends with each request."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import openai

import pynguin.configuration as config
from pynguin.large_language_model.client import OpenAIClient
from pynguin.large_language_model.request import RenderedRequest


class _FakeSecret:
    """Minimal stand-in for a pydantic SecretStr."""

    def get_secret_value(self) -> str:
        return "test-key"


def _make_client(monkeypatch, *, sampling_seed: bool = True, run_seed: int = 3) -> OpenAIClient:
    monkeypatch.setattr("pynguin.large_language_model.client.get_llm_url", lambda: None)
    monkeypatch.setattr("pynguin.large_language_model.client.openai.OpenAI", MagicMock)
    monkeypatch.setattr(config.configuration.large_language_model, "enable_response_caching", False)
    monkeypatch.setattr(config.configuration.large_language_model, "sampling_seed", sampling_seed)
    monkeypatch.setattr(config.configuration.seeding, "seed", run_seed)
    client = OpenAIClient(api_key=_FakeSecret(), model="test-model")
    client._client.chat.completions.create = MagicMock(
        return_value=_make_response("```python\nx = 1\n```")
    )
    return client


def _make_response(content: str) -> MagicMock:
    response = MagicMock()
    response.choices[0].message.content = content
    response.usage.prompt_tokens = 1
    response.usage.completion_tokens = 1
    return response


def _request(content: str = "hi") -> RenderedRequest:
    return RenderedRequest(
        messages=[{"role": "user", "content": content}], model="test-model", temperature=0.8
    )


def _sent_seeds(client: OpenAIClient) -> list[int | None]:
    return [
        call.kwargs.get("seed") for call in client._client.chat.completions.create.call_args_list
    ]


def test_no_seed_is_sent_by_default(monkeypatch):
    client = _make_client(monkeypatch, sampling_seed=False)

    client.send(_request())

    assert "seed" not in client._client.chat.completions.create.call_args.kwargs


def test_seed_is_a_non_negative_32_bit_integer(monkeypatch):
    client = _make_client(monkeypatch)

    client.send(_request())

    (seed,) = _sent_seeds(client)
    assert isinstance(seed, int)
    assert 0 <= seed < 2**31


def test_same_run_seed_and_content_give_the_same_seeds(monkeypatch):
    first = _make_client(monkeypatch)
    second = _make_client(monkeypatch)

    for client in (first, second):
        client.send(_request())
        client.send(_request())

    assert _sent_seeds(first) == _sent_seeds(second)


def test_repeated_requests_with_the_same_content_get_different_seeds(monkeypatch):
    client = _make_client(monkeypatch)

    client.send(_request())
    client.send(_request())

    first, second = _sent_seeds(client)
    assert first != second


def test_different_content_gets_a_different_seed(monkeypatch):
    client = _make_client(monkeypatch)

    client.send(_request("hi"))
    client.send(_request("bye"))

    first, second = _sent_seeds(client)
    assert first != second


def test_different_run_seeds_give_different_seeds(monkeypatch):
    first = _make_client(monkeypatch, run_seed=3)
    first.send(_request())
    second = _make_client(monkeypatch, run_seed=4)
    second.send(_request())

    assert _sent_seeds(first) != _sent_seeds(second)


def test_a_retry_reuses_the_seed_of_its_request(monkeypatch):
    client = _make_client(monkeypatch)
    monkeypatch.setattr(config.configuration.large_language_model, "max_retries", 2)
    monkeypatch.setattr("pynguin.large_language_model.client.time.sleep", lambda _: None)
    client._client.chat.completions.create.side_effect = [
        openai.OpenAIError("boom"),
        _make_response("```python\nx = 1\n```"),
    ]

    client.send(_request())

    first, second = _sent_seeds(client)
    assert first is not None
    assert first == second


def test_async_requests_get_the_same_seeds_as_sync_requests(monkeypatch):
    sync_client = _make_client(monkeypatch)
    sync_client.send(_request())
    async_client = _make_client(monkeypatch)
    async_create = AsyncMock(return_value=_make_response("```python\nx = 1\n```"))
    async_client._async_client = MagicMock()
    async_client._async_client.chat.completions.create = async_create

    asyncio.run(async_client.send_async(_request()))

    assert async_create.call_args.kwargs["seed"] == _sent_seeds(sync_client)[0]
