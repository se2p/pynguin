#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
from __future__ import annotations


def is_small(size: int) -> bool:
    """A helper that the package does not re-export."""
    return size < 10  # noqa: PLR2004


class widget:  # noqa: N801
    """A class named like its defining submodule (cf. croniter.croniter)."""

    def __init__(self, size: int) -> None:  # noqa: D107
        self.size = size

    def small(self) -> bool:
        """Whether the widget is small."""
        return is_small(self.size)
