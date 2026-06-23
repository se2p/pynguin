#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Tests for the OpenAI LLM client wrapper (llm_client.py)."""

from __future__ import annotations

import pytest

from pynguin.refinement import llm_client as llm_client_module
from pynguin.refinement.llm_client import LLMClient


class _FakeResponse:
    def __init__(self, status_code=200, payload=None, text="", headers=None):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text
        self.headers = headers or {}

    def json(self):
        return self._payload


@pytest.fixture
def client():
    return LLMClient(model_name="gpt-4o-mini", api_key="test-key")


def test_missing_api_key_raises(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="OpenAI API key required"):
        LLMClient(api_key=None)


def test_extract_code_from_python_block(client):
    text = "Here is the code:\n```python\nx = 1\n```"
    assert client._extract_code(text) == "x = 1"


def test_extract_code_from_plain_block(client):
    text = "```\ny = 2\n```"
    assert client._extract_code(text) == "y = 2"


def test_extract_code_without_block_returns_text(client):
    assert client._extract_code("  just text  ") == "just text"


def test_usage_counters_start_at_zero(client):
    assert client.get_usage() == {
        "calls": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "time_seconds": 0.0,
    }


def test_reset_usage(client):
    client._calls = 7
    client._input_tokens = 100
    client.reset_usage()
    assert client.get_usage()["calls"] == 0
    assert client.get_usage()["input_tokens"] == 0


def test_generate_code_happy_path(client, monkeypatch):
    payload = {
        "choices": [{"message": {"content": "```python\nresult = 42\n```"}}],
        "usage": {"prompt_tokens": 11, "completion_tokens": 4},
    }

    def fake_post(*_args, **_kwargs):
        return _FakeResponse(status_code=200, payload=payload)

    monkeypatch.setattr(llm_client_module.requests, "post", fake_post)

    code = client.generate_code("write something")
    assert code == "result = 42"
    usage = client.get_usage()
    assert usage["calls"] == 1
    assert usage["input_tokens"] == 11
    assert usage["output_tokens"] == 4


def test_generate_code_unexpected_error_returns_sentinel(client, monkeypatch):
    def fake_post(*_args, **_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(llm_client_module.requests, "post", fake_post)

    result = client.generate_code("write something")
    assert result.startswith("# LLM error")


def test_generate_code_retries_after_rate_limit(client, monkeypatch):
    monkeypatch.setattr(llm_client_module.time, "sleep", lambda _seconds: None)
    success_payload = {
        "choices": [{"message": {"content": "```python\nok = 1\n```"}}],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1},
    }
    responses = [
        _FakeResponse(status_code=429, headers={"Retry-After": "0"}),
        _FakeResponse(status_code=200, payload=success_payload),
    ]

    def fake_post(*_args, **_kwargs):
        return responses.pop(0)

    monkeypatch.setattr(llm_client_module.requests, "post", fake_post)

    result = client.generate_code("write something")
    assert result == "ok = 1"
    assert client.get_usage()["calls"] == 2


def test_generate_code_exhausts_retries_on_request_error(client, monkeypatch):
    monkeypatch.setattr(llm_client_module.time, "sleep", lambda _seconds: None)

    def fake_post(*_args, **_kwargs):
        raise llm_client_module.requests.exceptions.ConnectionError("down")

    monkeypatch.setattr(llm_client_module.requests, "post", fake_post)

    result = client.generate_code("write something")
    assert result == "# LLM error: request failed"
