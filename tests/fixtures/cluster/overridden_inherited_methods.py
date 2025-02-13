#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
from collections.abc import Iterator


class Foo:
    def __init__(self, a: list[int]) -> None:
        self._a = a

    def foo(self, x: int) -> int:
        return self._a[x]

    def __iter__(self) -> Iterator[int]:
        return iter(self._a)


class Bar(Foo):
    def foo(self, x: int) -> int:
        return self._a[x - 1]
