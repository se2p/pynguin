#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Fixture whose objects keep references to the standard input streams."""

import shlex
import sys


class StreamHolder:
    """Keeps the text and binary standard input streams."""

    def __init__(self) -> None:
        """Store the currently bound stdin and its binary buffer."""
        self.text = sys.stdin
        self.binary = sys.stdin.buffer
        self.name = "stdin"


def create_lexer() -> shlex.shlex:
    """Create a lexer that reads from the standard input.

    Returns:
        A lexer whose ``instream`` is ``sys.stdin``.
    """
    return shlex.shlex()
