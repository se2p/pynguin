#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
# No `from __future__ import annotations` here: the annotations of this module must be
# deferred (PEP 649), which is what these fixtures test.
import collections.abc
import functools
from typing import TYPE_CHECKING, Annotated, Optional  # noqa: UP035

from tests.fixtures.types.deferred_decorator import decorate

if TYPE_CHECKING:
    from collections.abc import Sized


def length(obj: Sized) -> int:
    return len(obj)


def pick(x: "int" | None, y: int) -> int:
    return y if x is None else x


def divide(x: 1 / 0) -> int:
    return x


class Box:
    def __init__(self, n: "int" | None) -> None:
        self.n = n

    def size(self, other: Sized) -> int:
        return len(other)


def nothing(x: "int" | None, z: "int") -> None:
    return None


def nested(x: list[Sized], y: int) -> None:
    return None


class Outer:
    class Inner:
        pass

    def method(self, x: Inner, y: Sized) -> Inner:
        return x


def make_closure():
    class Local:
        pass

    def closure(x: Local, y: Sized) -> Local:
        return x

    return closure


closure = make_closure()


def renamed(x: "int" | None, y: int) -> int:
    return y


renamed.__name__ = "public_name"


class Item:
    pass


@decorate
def decorated(x: "int" | None, y: Item) -> int:
    return 0


def callback(
    f: collections.abc.Callable[[int], Sized], g: collections.abc.Callable[..., Sized]
) -> None:
    return None


class Caller:
    def __call__(self, x: Sized) -> int:
        return 0


caller = Caller()

partial_length = functools.partial(length)


def nested_strings(
    x: "int" | None, y: list["Item"], z: Optional["Item"], w: Annotated[int, "meta"]  # noqa: UP045
) -> "Item":
    return Item()


class Record:
    a: "int" | None
    b: list["Item"]
    c: Annotated[int, "meta"]
