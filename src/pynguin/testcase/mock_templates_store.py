#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Shared store for mock decisions and templates used during test generation."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pynguin.mock_generation.mock_generator import MockTemplate

# Fully-qualified class names to mock when they appear as a parameter type.
MOCK_TARGETS: set[str] = set()
# Templates keyed by target, holding the proxy's return-value hints (optional).
MOCK_TEMPLATES_BY_TARGET: dict[str, MockTemplate] = {}
# Untyped parameters to mock directly (no type tracing): maps
# ``("<module>.<callable_qualname>", "<param_name>")`` to the boundary class FQN
# whose usage the untyped parameter statically matched.
MOCK_UNTYPED_PARAMS: dict[tuple[str, str], str] = {}
