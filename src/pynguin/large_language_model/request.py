# This file is part of the Pynguin automated unit test generation framework.
# Copyright (C) 2024-2026 Lukas Krodinger
# SPDX-License-Identifier: MIT

"""Provides the request representation for LLM interactions."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass


@dataclass(frozen=True)
class RenderedRequest:
    """A fully rendered request ready to be sent to an LLM."""

    messages: list[dict[str, str]]
    """The messages representing the chat history/context."""

    model: str
    """The name of the model to use."""

    temperature: float
    """The temperature for the request."""

    max_tokens: int | None = None
    """The maximum number of tokens to generate."""

    stop: list[str] | None = None
    """Up to 4 sequences where the API will stop generating further tokens."""

    def cache_key(self) -> str:
        """Computes a stable SHA-256 hash key of the request for caching.

        Returns:
            The SHA-256 hash key.
        """
        data = {
            "messages": self.messages,
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "stop": self.stop,
        }
        serialized = json.dumps(data, sort_keys=True)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
