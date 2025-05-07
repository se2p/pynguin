#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
from unittest.mock import patch

import pytest

from pynguin.large_language_model.caching import Cache
from pynguin.large_language_model.caching import sanitize_key


@pytest.fixture
def cache(tmp_path):
    with patch("tempfile.gettempdir", return_value=str(tmp_path)):
        cache_instance = Cache()
        yield cache_instance


def test_set_and_get_value(cache):
    key = "myKey"
    value = "cachedValue"
    cache.set(key, value)
    assert cache.get(key) == value


def test_get_returns_none_when_key_not_set(cache):
    assert cache.get("nonexistent") is None


def test_overwrite_existing_key(cache):
    key = "duplicate"
    cache.set(key, "first")
    cache.set(key, "second")
    assert cache.get(key) == "second"


def test_clear_removes_all_cache_files(cache):
    cache.set("key1", "value1")
    cache.set("key2", "value2")
    assert cache.get("key1") == "value1"
    assert cache.get("key2") == "value2"
    cache.clear()
    assert cache.get("key1") is None
    assert cache.get("key2") is None


def test_sanitize_key_is_hash():
    key = "my key with spaces and symbols!@#"
    result = sanitize_key(key)
    assert isinstance(result, str)
    assert len(result) == 64  # SHA-256 hex digest length
    assert all(c in "0123456789abcdef" for c in result)
