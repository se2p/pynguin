#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""An enum that dill cannot pickle by value, modelled after ``pypara``'s ``Direction``."""

from __future__ import annotations

from enum import Enum


class Direction(Enum):
    """Pickling this class by value recurses into itself via ``of``."""

    INC = +1
    DEC = -1

    @classmethod
    def of(cls, quantity: int) -> Direction:
        """Returns the direction for the sign of the quantity.

        Args:
            quantity: The quantity

        Returns:
            The direction
        """
        return Direction.INC if quantity > 0 else Direction.DEC
