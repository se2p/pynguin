#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides a basic API to communicate with LLMs."""

from __future__ import annotations

import enum

from pynguin.large_language_model.client import extract_python_code


class LLMProvider(str, enum.Enum):
    """An enum for the available LLM service providers."""

    OPENAI = "openai"


def extract_code(llm_response: str) -> str:
    """Takes the response from the LLM and attempts to extract the answer.

    Args:
        llm_response: the response from the LLM

    Returns:
        the extracted answer, i.e., the extracted pytest code
    """
    return extract_python_code(llm_response)
