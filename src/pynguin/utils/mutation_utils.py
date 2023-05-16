#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2023 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Provides some mutation related utilities."""
from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from pynguin.utils import randomness


T = TypeVar("T")  # pylint:disable=invalid-name


def alpha_exponent_insertion(
    elements: list[T],
    value_supplier: Callable[[], T | None],
    alpha: float = 0.5,
    exponent: int = 0,
) -> bool:
    """Provides an alpha-exponent insertion algorithm.

    Repeatedly inserts a new element generated by value_supplier into the given
    elements at a random position as long as next_float() < alpha^exponent holds.
    Exponent is increased after each insertion, thus lowering the chance for another
    insertion.

    Args:
        elements: the elements into which new elements should be inserted.
        value_supplier: supplies the elements that are inserted.
        alpha: the used alpha value.
        exponent: start value of the exponent.

    Returns:
        True, iff at least one element was inserted.
    """
    assert 0 < alpha < 1
    pos = 0
    changed = False
    while randomness.next_float() <= pow(alpha, exponent):
        # Randomize the position for each insertion.
        if len(elements) > 0:
            pos = randomness.next_int(0, len(elements) + 1)

        exponent += 1
        value = value_supplier()
        if value is None:
            # Supplier is exhausted
            return changed

        elements.insert(
            pos,
            value,
        )
        changed = True

    return changed
