# This file is part of Pynguin.
#
# SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
# SPDX-License-Identifier: MIT

"""Configuration schema for LLM Prompts."""

from __future__ import annotations

import dataclasses
from typing import Any


@dataclasses.dataclass(frozen=True)
class PromptConfig:
    """Configuration and template definitions for a specific prompt type."""

    system_message: str | None = None
    user_message_template: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    stop: list[str] | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PromptConfig:
        """Constructs a PromptConfig from a dictionary with strict key validation.

        Args:
            data: The raw dictionary loaded from YAML.

        Returns:
            A PromptConfig instance.

        Raises:
            ValueError: If an unknown key is present in data.
        """
        allowed = {f.name for f in dataclasses.fields(cls)}
        unknown = set(data.keys()) - allowed
        if unknown:
            raise ValueError(f"Unknown prompt configuration key(s): {unknown}")
        return cls(**data)
