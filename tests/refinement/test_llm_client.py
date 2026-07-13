#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Tests for the OpenAI LLM client wrapper (llm_client.py)."""

from __future__ import annotations

import types

import pytest

import pynguin.configuration as config
from pynguin.refinement import llm_client as llm_client_module
from pynguin.refinement.llm_client import (
    LLMClient,
    _extract_code,  # noqa: PLC2701
)

pytestmark = pytest.mark.skipif(
    not llm_client_module.OPENAI_AVAILABLE,
    reason="openai extra not installed",
)


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _make_response(content, prompt_tokens=11, completion_tokens=4):
    """Build a minimal object shaped like an OpenAI chat completion."""
    message = types.SimpleNamespace(content=content)
    choice = types.SimpleNamespace(message=message)
    usage = types.SimpleNamespace(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
    )
    return types.SimpleNamespace(choices=[choice], usage=usage)


def _patch_create(monkeypatch, fake_create):
    """Replace ``openai.chat.completions.create`` with ``fake_create``."""
    fake_chat = types.SimpleNamespace(completions=types.SimpleNamespace(create=fake_create))
    monkeypatch.setattr(llm_client_module.openai, "chat", fake_chat)


@pytest.fixture(autouse=True)
def _no_live_api_key(monkeypatch):
    """Avoid the live key validation performed in ``LLMClient.__init__``."""
    monkeypatch.setattr(llm_client_module, "set_api_key", lambda: None)


@pytest.fixture
def client():
    return LLMClient(model_name="gpt-4o-mini")


# ---------------------------------------------------------------------------
# _extract_code
# ---------------------------------------------------------------------------


def test_extract_code_from_python_block():
    assert _extract_code("Here:\n```python\nx = 1\n```") == "x = 1"


def test_extract_code_from_plain_block():
    assert _extract_code("```\ny = 2\n```") == "y = 2"


def test_extract_code_without_block_returns_stripped_text():
    assert _extract_code("  just text  ") == "just text"


# ---------------------------------------------------------------------------
# construction / usage counters
# ---------------------------------------------------------------------------


def test_model_defaults_to_configuration(monkeypatch):
    monkeypatch.setattr(config.configuration.large_language_model, "model_name", "cfg-model")
    assert LLMClient().model == "cfg-model"


def test_explicit_model_name_wins(client):
    assert client.model == "gpt-4o-mini"


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
    client._output_tokens = 50
    client._time_seconds = 1.5
    client.reset_usage()
    assert client.get_usage() == {
        "calls": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "time_seconds": 0.0,
    }


# ---------------------------------------------------------------------------
# generate_code
# ---------------------------------------------------------------------------


def test_generate_code_happy_path(client, monkeypatch):
    def fake_create(**_kwargs):
        return _make_response("```python\nresult = 42\n```")

    _patch_create(monkeypatch, fake_create)

    code = client.generate_code("write something")
    assert code == "result = 42"
    usage = client.get_usage()
    assert usage["calls"] == 1
    assert usage["input_tokens"] == 11
    assert usage["output_tokens"] == 4


def test_generate_code_unexpected_error_returns_sentinel(client, monkeypatch):
    def fake_create(**_kwargs):
        raise RuntimeError("boom")

    _patch_create(monkeypatch, fake_create)

    result = client.generate_code("write something")
    assert result == "# LLM error: unable to generate code"


def test_generate_code_retries_after_rate_limit(client, monkeypatch):
    monkeypatch.setattr(llm_client_module.time, "sleep", lambda _seconds: None)

    class _FakeRateLimitError(Exception):
        pass

    monkeypatch.setattr(llm_client_module, "_RATE_LIMIT_ERRORS", (_FakeRateLimitError,))

    attempts = {"n": 0}

    def fake_create(**_kwargs):
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise _FakeRateLimitError
        return _make_response("```python\nok = 1\n```", prompt_tokens=1, completion_tokens=1)

    _patch_create(monkeypatch, fake_create)

    result = client.generate_code("write something")
    assert result == "ok = 1"
    # The failed attempt and the successful one both increment the call counter.
    assert client.get_usage()["calls"] == 2


def test_generate_code_exhausts_retries_on_api_error(client, monkeypatch):
    monkeypatch.setattr(llm_client_module.time, "sleep", lambda _seconds: None)

    class _FakeApiError(Exception):
        pass

    monkeypatch.setattr(llm_client_module, "_API_ERRORS", (_FakeApiError,))

    def fake_create(**_kwargs):
        raise _FakeApiError("down")

    _patch_create(monkeypatch, fake_create)

    result = client.generate_code("write something")
    assert result == "# LLM error: request failed"


def test_generate_code_exhausts_retries_on_rate_limit(client, monkeypatch):
    monkeypatch.setattr(llm_client_module.time, "sleep", lambda _seconds: None)

    class _AlwaysRateLimitError(Exception):
        pass

    monkeypatch.setattr(llm_client_module, "_RATE_LIMIT_ERRORS", (_AlwaysRateLimitError,))

    def fake_create(**_kwargs):
        raise _AlwaysRateLimitError("slow down")

    _patch_create(monkeypatch, fake_create)

    result = client.generate_code("write something")
    assert result == "# LLM error: rate limited"
