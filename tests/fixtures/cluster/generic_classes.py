#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
from __future__ import annotations

from typing import Generic, TypeVar

T = TypeVar("T")
K = TypeVar("K")
V = TypeVar("V")


class Box(Generic[T]):
    """A generic container."""

    def __init__(self, value: T) -> None:
        self.value = value

    def get_value(self) -> T:
        return self.value

    def set_value(self, new_val: T) -> None:
        self.value = new_val


class KeyValue(Generic[K, V]):
    """A generic key-value pair."""

    def __init__(self, key: K, value: V) -> None:
        self.key = key
        self.value = value

    def get_key(self) -> K:
        return self.key

    def get_value(self) -> V:
        return self.value


def identity(x: T) -> T:
    """A generic identity function."""
    return x
