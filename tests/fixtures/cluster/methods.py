#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""A fixture module exercising classmethod, staticmethod, and method discovery."""

from __future__ import annotations

import functools


class ClassWithMethods:
    """A class containing different kinds of methods."""

    def __init__(self, value: int = 0) -> None:
        self.value = value

    def normal_method(self, x: int) -> int:
        """A regular instance method."""
        return self.value + x

    @staticmethod
    def static_method(x: int) -> int:
        """A static method."""
        return x * 2

    @classmethod
    def class_method(cls, x: int) -> int:
        """A class method."""
        return x + 10

    @classmethod
    def factory(cls, value: int) -> ClassWithMethods:
        """A classmethod acting as factory."""
        return cls(value)

    @functools.lru_cache
    def cached_method(self, x: int) -> int:
        """A cache-wrapped instance method."""
        return self.value + x

    @staticmethod
    @functools.lru_cache
    def cached_static(x: int) -> int:
        """A cache-wrapped static method."""
        return x * 3

    @classmethod
    @functools.lru_cache
    def cached_classmethod(cls, x: int) -> int:
        """A cache-wrapped class method."""
        return x * 4
