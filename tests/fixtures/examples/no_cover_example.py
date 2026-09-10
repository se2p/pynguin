#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
"""Example functions with pragma and pynguin no cover."""

from __future__ import annotations


def no_cover_double_if(x: bool) -> bool:
    """Return boolean with first branch excluded via pragma no cover."""
    if x:  # pragma: no cover
        return True
    if not x:
        return False
    return False
