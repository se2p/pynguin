#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""Classes whose constructor parameters are (partly) defined by ``__new__``."""

from __future__ import annotations


class OnlyNew:
    def __new__(cls, size: int):
        """Creates a box.

        Raises:
            ValueError: if size is negative.
        """
        if size < 0:
            raise ValueError
        obj = super().__new__(cls)
        obj.size = size
        return obj


class GenericNewSpecificInit:
    _instance = None

    def __new__(cls, *args, **kwargs):
        return super().__new__(cls)

    def __init__(self, x: int) -> None:
        self.x = x


class SpecificNewGenericInit:
    def __new__(cls, x: int):
        return super().__new__(cls)

    def __init__(self, *args, **kwargs) -> None:
        pass


class Style(str):
    def __new__(cls, *rules: str, value: str = ""):
        return super().__new__(cls, value)


class InitOverridesInheritedNew(OnlyNew):
    def __init__(self, size: int, extra: str = "") -> None:
        self.extra = extra


class InheritsNew(OnlyNew):
    def method(self) -> int:
        return 1


class OnlyInit:
    def __init__(self, y: float) -> None:
        self.y = y


class NoConstructor:
    pass


class DictAndPython(dict, OnlyInit):
    pass
