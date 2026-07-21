#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Tests for the new request-hash based LLMCache."""

import json

import pytest

import pynguin.configuration as config
from pynguin.large_language_model.cache import LLMCache
from pynguin.large_language_model.request import RenderedRequest


@pytest.fixture
def temp_cache_dir(tmp_path):
    return tmp_path / "cache_dir"


def test_cache_init_defaults(monkeypatch, temp_cache_dir):
    monkeypatch.setattr(
        config.configuration.large_language_model, "cache_dir", str(temp_cache_dir), raising=False
    )

    cache = LLMCache()
    assert cache.cache_dir == temp_cache_dir
    assert temp_cache_dir.exists()


def test_cache_get_set_miss_hit(temp_cache_dir):
    cache = LLMCache(cache_dir=temp_cache_dir)

    request = RenderedRequest(
        messages=[{"role": "user", "content": "hello"}],
        model="gpt-test",
        temperature=0.5,
        max_tokens=100,
        stop=["\n"],
    )

    # Cache miss
    assert cache.get(request) is None

    # Cache set
    response = "hello back"
    cache.set(request, response)

    # Cache hit
    assert cache.get(request) == response

    # Check that cache file exists with the json payload
    cache_file = cache._get_cache_file(request)
    assert cache_file.exists()

    data = json.loads(cache_file.read_text(encoding="utf-8"))
    assert data["response"] == response
    assert data["request"]["model"] == "gpt-test"
    assert data["request"]["temperature"] == 0.5


def test_cache_key_variation_miss(temp_cache_dir):
    cache = LLMCache(cache_dir=temp_cache_dir)

    req1 = RenderedRequest(
        messages=[{"role": "user", "content": "hello"}], model="gpt-test", temperature=0.5
    )
    req2 = RenderedRequest(
        messages=[{"role": "user", "content": "hello"}],
        model="gpt-test",
        temperature=0.6,  # different temperature
    )

    cache.set(req1, "response1")
    assert cache.get(req1) == "response1"
    assert cache.get(req2) is None  # should miss due to different temperature


def test_cache_clear(temp_cache_dir):
    cache = LLMCache(cache_dir=temp_cache_dir)

    req1 = RenderedRequest(
        messages=[{"role": "user", "content": "hello"}], model="gpt-test", temperature=0.5
    )
    cache.set(req1, "response1")

    # Clear cache
    cache.clear()
    assert cache.get(req1) is None
    assert not list(temp_cache_dir.glob("*.json"))
