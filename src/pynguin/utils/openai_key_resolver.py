#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Utilities for resolving and validating OpenAI API keys."""

import logging
import os

import pynguin.configuration as config

try:
    import openai
    from dotenv import load_dotenv

    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False


_logger = logging.getLogger(__name__)


def get_api_key_from_env() -> str:
    """Resolve OpenAI API key from environment variables and .env file.

    Preference order:
    1) PYNGUIN_OPENAI_API_KEY
    2) OPENAI_API_KEY
    """
    load_dotenv()
    for var in ("PYNGUIN_OPENAI_API_KEY", "OPENAI_API_KEY"):
        value = os.environ.get(var, "")
        if value and value.strip():
            return value.strip()
    return ""


def get_resolved_api_key() -> str:
    """Return the effective OpenAI API key from config or environment.

    Preference order:
    1) configuration.large_language_model.api_key (if non-empty)
    2) PYNGUIN_OPENAI_API_KEY
    3) OPENAI_API_KEY
    """
    cfg_key = getattr(config.configuration.large_language_model, "api_key", "") or ""
    cfg_key = cfg_key.strip()
    if cfg_key:
        return cfg_key
    return get_api_key_from_env()


def is_api_key_present() -> bool:
    """Checks if the OpenAI API key is present and not an empty string.

    Returns:
        bool: True if the API key is present and not empty, False otherwise.
    """
    return bool(get_resolved_api_key())


def is_api_key_valid() -> bool:
    """Checks if the provided OpenAI API key is valid.

    Returns:
        bool: True if the API key is valid, False otherwise.

    Raises:
        openai.OpenAIError: If the API key is invalid or another error occurs.
    """
    try:
        openai.api_key = get_resolved_api_key()
        openai.models.list()  # This would raise an error if the API key is invalid
        return True
    except openai.OpenAIError:
        return False


def set_api_key():
    """Sets the OpenAI API key from config or environment if it is valid.

    Raises:
        ValueError: If the OpenAI API key is missing or invalid.
    """
    if not OPENAI_AVAILABLE:
        raise ValueError(
            "OpenAI API library is not available. You can install it with poetry "
            "install --with openai."
        )
    if not is_api_key_present():
        raise ValueError("OpenAI API key is missing.")

    api_key = get_resolved_api_key()
    if is_api_key_valid():
        openai.api_key = api_key
    else:
        raise ValueError("OpenAI API key is invalid.")
