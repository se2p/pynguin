#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Utilities for resolving OpenAI API keys."""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pydantic import SecretStr
else:
    try:
        from pydantic import SecretStr
    except ImportError:
        SecretStr = str

import pynguin.configuration as config

try:
    from dotenv import load_dotenv

    DOTENV_AVAILABLE = True
except ImportError:
    DOTENV_AVAILABLE = False

_logger = logging.getLogger(__name__)


def get_api_key() -> SecretStr | None:
    """Get OpenAI API key with clear preference order.

    Preference order:
    1) configuration.large_language_model.api_key (if non-empty)
    2) PYNGUIN_OPENAI_API_KEY environment variable
    3) OPENAI_API_KEY environment variable

    Returns:
        SecretStr with the API key or None if not found.
    """
    # Check config first
    cfg_key = getattr(config.configuration.large_language_model, "api_key", "") or ""
    cfg_key = cfg_key.strip()
    if cfg_key:
        return SecretStr(cfg_key)

    # Load .env file if dotenv is available
    if DOTENV_AVAILABLE:
        load_dotenv()

    # Check environment variables
    for var in ("PYNGUIN_OPENAI_API_KEY", "OPENAI_API_KEY"):
        value = os.environ.get(var, "")
        if value and value.strip():
            return SecretStr(value.strip())

    return None


def require_api_key() -> SecretStr:
    """Get OpenAI API key or raise ValueError if not found.

    Returns:
        SecretStr with the API key.

    Raises:
        ValueError: If the API key is not found in config or environment.
    """
    api_key = get_api_key()
    if api_key is None or not api_key.get_secret_value():
        _logger.error("OpenAI API key not found in configuration or environment.")
        raise ValueError(
            "OpenAI API key not found. Set it via:\n"
            "  - configuration.large_language_model.api_key, or\n"
            "  - PYNGUIN_OPENAI_API_KEY environment variable, or\n"
            "  - OPENAI_API_KEY environment variable"
        )
    return api_key


def is_api_key_present() -> bool:
    """Check if the OpenAI API key is available.

    Returns:
        True if the API key is present and not empty, False otherwise.
    """
    return get_api_key() is not None
