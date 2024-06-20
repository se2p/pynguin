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

    def __init__(self, module_code: str, module_path: str):
        """Creates a new prompt.

        Args:
            module_code: the module code to be passed to the prompt.
            module_path: the module path to be passed to the prompt.
        """
        self.module_code = module_code
        self.module_path = module_path

    @abstractmethod
    def build_prompt(self) -> str:
        """Builds prompt message."""
