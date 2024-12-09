#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2024 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides the LLM prompt."""
from abc import abstractmethod


class Prompt:
    """Base LLM prompt class."""

    @abstractmethod
    def build_prompt(self) -> str:
        """Builds prompt message."""
