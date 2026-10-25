#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Fixture with an abstract class that only its own abstract methods can generate.

Mirrors the shape of the ``numbers`` ABCs: no concrete subclass exists, so every
generator of ``Expression`` needs an ``Expression`` receiver.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class Expression(ABC):
    """Abstract expression without any concrete subclass."""

    @abstractmethod
    def simplify(self) -> Expression:
        """Simplify the expression."""

    @abstractmethod
    def negate(self) -> Expression:
        """Negate the expression."""

    @abstractmethod
    def expand(self) -> Expression:
        """Expand the expression."""

    @abstractmethod
    def derive(self) -> Expression:
        """Derive the expression."""


def evaluate(expression: Expression) -> int:
    """Evaluate the expression.

    Args:
        expression: The expression to evaluate.

    Returns:
        The value of the expression.
    """
    return 0 if expression is None else 1
