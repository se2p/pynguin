# This file is part of Pynguin.
#
# SPDX-FileCopyrightText: 2019–2024 Pynguin Contributors
#
# SPDX-License-Identifier: MIT
#
"""This module provides a simple caching mechanism using the filesystem."""

import hashlib
import pathlib
import tempfile


def sanitize_key(key: str) -> str:
    """Sanitizes the key to create a valid filename by hashing it.

    Args:
        key: The key to sanitize.

    Returns:
        A sanitized filename string.
    """
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


class Cache:
    """A simple file-based cache implementation."""

    def __init__(self):
        """Initializes the cache using a directory in a temporary location."""
        self.cache_dir = pathlib.Path(tempfile.gettempdir()) / "pynguin"
        self.cache_dir.mkdir(exist_ok=True)

    def _get_cache_file(self, key: str) -> pathlib.Path:
        """Generates a cache file path for a given key.

        Args:
            key: The key for which to generate the cache file path.

        Returns:
            The path to the cache file.
        """
        sanitized_key = sanitize_key(key)
        return self.cache_dir / f"{sanitized_key}.cache"

    def get(self, key: str) -> str | None:
        """Retrieves the value for a given key from the cache.

        Args:
            key: The key to look up in the cache.

        Returns:
            The cached value if it exists, else None.
        """
        cache_file = self._get_cache_file(key)
        if cache_file.exists():
            return cache_file.read_text()
        return None

    def set(self, key: str, value: str):
        """Sets the value for a given key in the cache.

        Args:
            key: The key for which to set the value.
            value: The value to cache.
        """
        cache_file = self._get_cache_file(key)
        cache_file.write_text(value)

    def clear(self):
        """Clears all entries in the cache."""
        for cache_file in self.cache_dir.glob("*.cache"):
            cache_file.unlink()
