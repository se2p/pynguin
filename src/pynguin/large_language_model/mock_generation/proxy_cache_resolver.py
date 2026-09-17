#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Utilities for resolving the mock-cache proxy URL.

Preference order:
1. ``configuration.mock_generation.proxy_cache_url`` (if non-empty)
2. ``PYNGUIN_PROXY_CACHE_URL`` environment variable
"""

from __future__ import annotations

import logging
import os

import pynguin.configuration as config

try:
    from dotenv import load_dotenv

    DOTENV_AVAILABLE = True
except ImportError:
    DOTENV_AVAILABLE = False

_logger = logging.getLogger(__name__)


def get_proxy_cache_url() -> str | None:
    """Return the mock-cache proxy base URL, or ``None`` if not configured.

    Preference order:
    1. ``configuration.mock_generation.proxy_cache_url`` (if non-empty)
    2. ``PYNGUIN_PROXY_CACHE_URL`` environment variable

    Returns:
        URL string, or ``None`` if neither source provides a value.
    """
    cfg_url = getattr(config.configuration.mock_generation, "proxy_cache_url", "") or ""
    if cfg_url.strip():
        return cfg_url.strip()

    if DOTENV_AVAILABLE:
        load_dotenv()

    value = os.environ.get("PYNGUIN_PROXY_CACHE_URL", "").strip()
    return value or None


def require_proxy_cache_url() -> str:
    """Return the mock-cache proxy base URL or raise if not configured.

    Returns:
        URL string.

    Raises:
        RuntimeError: If neither the config field nor the environment variable is set.
    """
    url = get_proxy_cache_url()
    if not url:
        _logger.error("Mock-cache proxy URL not found in configuration or environment.")
        raise RuntimeError(
            "Mock-cache proxy URL not found. Set it via:\n"
            "  - configuration.mock_generation.proxy_cache_url, or\n"
            "  - PYNGUIN_PROXY_CACHE_URL environment variable"
        )
    return url
