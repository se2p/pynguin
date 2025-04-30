#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Tests for the caching module."""

import pathlib

from unittest.mock import patch

import pytest

from pynguin.large_language_model.caching import Cache
from pynguin.large_language_model.caching import sanitize_key


@pytest.fixture
def cache(tmp_path):
    """Fixture to create a cache instance with a temporary directory."""
    with patch("tempfile.gettempdir", return_value=str(tmp_path)):
        cache_instance = Cache()
        yield cache_instance


def test_sanitize_key():
    """Test that sanitize_key returns a SHA-256 hash of the input string."""
    key = "test key"
    result = sanitize_key(key)
    assert isinstance(result, str)
    assert len(result) == 64  # SHA-256 hex digest length
    assert all(c in "0123456789abcdef" for c in result)


def test_cache_init(tmp_path):
    """Test that the Cache.__init__ method creates the cache directory."""
    # Mock tempfile.gettempdir to return our tmp_path
    with patch("tempfile.gettempdir", return_value=str(tmp_path)):
        cache = Cache()
        # Check that the cache directory was created
        assert cache.cache_dir == pathlib.Path(tmp_path) / "pynguin"
        assert cache.cache_dir.exists()
        assert cache.cache_dir.is_dir()


def test_get_cache_file(cache):
    """Test that _get_cache_file returns the correct path."""
    key = "test key"
    sanitized = sanitize_key(key)
    cache_file = cache._get_cache_file(key)

    # Check that the cache file path is correct
    assert cache_file == cache.cache_dir / f"{sanitized}.cache"
    # Check that sanitize_key was used
    assert sanitized in str(cache_file)


def test_get_existing_file(cache):
    """Test that get returns the content of an existing cache file."""
    key = "test key"
    value = "test value"

    # Create the cache file directly
    cache_file = cache._get_cache_file(key)
    cache_file.write_text(value)

    # Check that get returns the content
    assert cache.get(key) == value


def test_get_nonexistent_file(cache):
    """Test that get returns None for a nonexistent cache file."""
    key = "nonexistent key"

    # Check that the cache file doesn't exist
    cache_file = cache._get_cache_file(key)
    assert not cache_file.exists()

    # Check that get returns None
    assert cache.get(key) is None


def test_set_creates_file(cache):
    """Test that set creates a cache file with the correct content."""
    key = "test key"
    value = "test value"

    # Set the value
    cache.set(key, value)

    # Check that the cache file was created with the correct content
    cache_file = cache._get_cache_file(key)
    assert cache_file.exists()
    assert cache_file.read_text() == value


def test_clear_removes_files(cache):
    """Test that clear removes all cache files."""
    # Create some cache files
    cache.set("key1", "value1")
    cache.set("key2", "value2")

    # Check that the cache files exist
    assert list(cache.cache_dir.glob("*.cache"))

    # Clear the cache
    cache.clear()

    # Check that no cache files remain
    assert not list(cache.cache_dir.glob("*.cache"))
