# This file is part of the Pynguin automated unit test generation framework.
# Copyright (C) 2019–2026 Pynguin Contributors
# SPDX-License-Identifier: MIT
#
"""Provides utilities for naming things in the generated code."""

from __future__ import annotations


def get_module_alias(module_name: str) -> str:
    """Return the alias used for the module under test.

    Appends a trailing underscore to avoid name collisions with package members.

    Args:
        module_name: The name of the module under test.

    Returns:
        The alias to use in generated code.
    """
    return module_name.rsplit(".", 1)[-1] + "_"
