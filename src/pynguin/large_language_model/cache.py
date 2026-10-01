# This file is part of Pynguin.
#
# SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
# SPDX-License-Identifier: MIT
#

"""Provides caching mechanism for LLM responses."""

from __future__ import annotations

import datetime
import json
import logging
import os
import pathlib
import uuid
from typing import TYPE_CHECKING

import pynguin.configuration as config

if TYPE_CHECKING:
    from pynguin.large_language_model.request import RenderedRequest

_logger = logging.getLogger(__name__)


class LLMCache:
    """A file-based cache that keys on RenderedRequest hashes.

    Content-keyed and seed-agnostic: two requests with identical rendered content
    hit the same entry regardless of which run or seed produced them. There is no
    seed-aware invalidation here -- whether reusing a cache_dir across seed
    repetitions is appropriate is the caller's call, not something this class
    enforces. Safe for concurrent writers (parallel islands, or a shared
    cache_dir across parallel runs) via the atomic write in set().
    """

    def __init__(self, cache_dir: pathlib.Path | None = None) -> None:
        """Initializes the cache.

        Args:
            cache_dir: The directory to store cached responses. If not provided,
                       attempts to read from configuration or defaults to
                       ~/.cache/pynguin/llm.
        """
        if cache_dir is not None:
            self._cache_dir = cache_dir
        else:
            cfg_cache_dir = getattr(config.configuration.large_language_model, "cache_dir", None)
            if cfg_cache_dir:
                self._cache_dir = pathlib.Path(cfg_cache_dir).expanduser()
            else:
                self._cache_dir = pathlib.Path("~/.cache/pynguin/llm").expanduser()

        self._cache_dir.mkdir(parents=True, exist_ok=True)

    @property
    def cache_dir(self) -> pathlib.Path:
        """Returns the cache directory path."""
        return self._cache_dir

    def _get_cache_file(self, request: RenderedRequest) -> pathlib.Path:
        key = request.cache_key()
        return self._cache_dir / f"{key}.json"

    def get(self, request: RenderedRequest) -> str | None:
        """Retrieves a response from cache for the given request.

        Args:
            request: The RenderedRequest to look up.

        Returns:
            The cached response string or None if not cached.
        """
        cache_file = self._get_cache_file(request)
        if cache_file.exists():
            try:
                data = json.loads(cache_file.read_text(encoding="utf-8"))
                return data.get("response")
            except (json.JSONDecodeError, OSError) as exc:
                _logger.warning("Failed to read cache file %s: %s", cache_file, exc)
        return None

    def set(self, request: RenderedRequest, response: str) -> None:
        """Saves a response to the cache.

        Writes to a uniquely-named temp file then os.replace()s it into place --
        atomic on POSIX/Windows for same-filesystem renames, so concurrent writers
        (parallel islands, parallel seed repetitions sharing the same cache_dir)
        never observe a partially-written or corrupted cache file.

        Args:
            request: The RenderedRequest trigger.
            response: The response string.
        """
        cache_file = self._get_cache_file(request)
        data = {
            "request": {
                "messages": request.messages,
                "model": request.model,
                "temperature": request.temperature,
                "max_tokens": request.max_tokens,
                "stop": request.stop,
            },
            "response": response,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "model": request.model,
        }
        tmp_file = cache_file.with_suffix(f".json.tmp.{os.getpid()}.{uuid.uuid4().hex}")
        try:
            tmp_file.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
            tmp_file.replace(cache_file)
        except OSError as exc:
            _logger.warning("Failed to write cache file %s: %s", cache_file, exc)
            tmp_file.unlink(missing_ok=True)

    def clear(self) -> None:
        """Clears all json cache entries."""
        for cache_file in self._cache_dir.glob("*.json"):
            try:
                cache_file.unlink()
            except OSError as exc:  # noqa: PERF203
                _logger.warning("Failed to delete cache file %s: %s", cache_file, exc)
