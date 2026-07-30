# This file is part of Pynguin.
#
# SPDX-FileCopyrightText: 2019–2024 Pynguin Contributors
#
# SPDX-License-Identifier: MIT
#
"""Helper function for LLM parser."""

import logging

logger = logging.getLogger(__name__)


def add_line_numbers(original: str) -> str:
    """Adds line numbers to the input string.

    Args:
        original: The input string to add line numbers to.

    Returns:
        The input string with line numbers added.
    """
    lines = original.splitlines()
    numbered_lines = [f"{i + 1}: {line}" for i, line in enumerate(lines)]
    return "\n".join(numbered_lines)
