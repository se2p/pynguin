#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Tests for the ``enable_thinking`` extra_body passthrough in the OpenAI client."""

from unittest.mock import MagicMock

import pynguin.configuration as config
from pynguin.large_language_model.client import OpenAIClient
from pynguin.large_language_model.request import RenderedRequest


class _FakeSecret:
    """Minimal stand-in for a pydantic SecretStr."""

    def get_secret_value(self) -> str:
        return "test-key"


def _make_client(monkeypatch) -> OpenAIClient:
    monkeypatch.setattr("pynguin.large_language_model.client.get_llm_url", lambda: None)
    monkeypatch.setattr("pynguin.large_language_model.client.openai.OpenAI", MagicMock)
    monkeypatch.setattr(config.configuration.large_language_model, "enable_response_caching", False)
    return OpenAIClient(api_key=_FakeSecret(), model="test-model")


def _make_response(content: str) -> MagicMock:
    response = MagicMock()
    response.choices[0].message.content = content
    response.usage.prompt_tokens = 1
    response.usage.completion_tokens = 1
    return response


def _request(*, enable_thinking: bool | None) -> RenderedRequest:
    return RenderedRequest(
        messages=[{"role": "user", "content": "hi"}],
        model="test-model",
        temperature=0.5,
        enable_thinking=enable_thinking,
    )


def test_enable_thinking_unset_omits_extra_body(monkeypatch):
    client = _make_client(monkeypatch)
    create = MagicMock(return_value=_make_response("```python\nx = 1\n```"))
    client._client.chat.completions.create = create

    client.send(_request(enable_thinking=None))

    assert "extra_body" not in create.call_args.kwargs


def test_enable_thinking_false_sets_extra_body(monkeypatch):
    client = _make_client(monkeypatch)
    create = MagicMock(return_value=_make_response("```python\nx = 1\n```"))
    client._client.chat.completions.create = create

    client.send(_request(enable_thinking=False))

    assert create.call_args.kwargs["extra_body"] == {
        "chat_template_kwargs": {"enable_thinking": False}
    }


def test_enable_thinking_true_sets_extra_body(monkeypatch):
    client = _make_client(monkeypatch)
    create = MagicMock(return_value=_make_response("```python\nx = 1\n```"))
    client._client.chat.completions.create = create

    client.send(_request(enable_thinking=True))

    assert create.call_args.kwargs["extra_body"] == {
        "chat_template_kwargs": {"enable_thinking": True}
    }
