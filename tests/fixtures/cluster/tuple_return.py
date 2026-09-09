#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Fixture for testing tuple return types and deconstruction."""

from __future__ import annotations


class Foo:
    """A sample Foo class."""

    def __init__(self, val: int) -> None:
        self.val = val

    def get_val(self) -> int:
        """Return the stored value."""
        return self.val


class Bar:
    """A sample Bar class."""

    def __init__(self, text: str) -> None:
        self.text = text

    def is_empty(self) -> bool:
        """Check if text is empty."""
        return len(self.text) == 0


def give_me_a_tuple() -> tuple[Foo, Bar]:
    """Return a tuple of (Foo, Bar)."""
    return Foo(42), Bar("hello")


def use_bar(bar: Bar) -> bool:
    """Consume a Bar instance."""
    return not bar.is_empty()
