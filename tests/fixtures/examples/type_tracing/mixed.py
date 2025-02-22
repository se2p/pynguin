#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
from tests.fixtures.examples.type_tracing.large_test_cluster import *  # noqa: F403,F401


def multiple_unknowns(
    a: "Foo96 | Bar96", b: "Foo30 | Bar30", c: float  # noqa: F405
) -> int:
    if a.attribute_96 > b.attribute_30 + c:
        return 42
    return 0


def instance_check(x: Circle | str, y: int) -> int:  # noqa: F405
    some_list = [x]
    for foo in some_list:
        if isinstance(foo, Circle) and foo.r * y > 100:  # noqa: F405
            return 42
    return 0


def only_args(*args: "Foo0 | Bar0") -> int:  # noqa: F405
    for v in args:
        if v.attribute_0:
            return 0
        return 42
    return 0


def only_kwargs(**kwargs: "Foo0 | Bar0") -> int:  # noqa: F405
    for v, k in kwargs.items():
        if k.attribute_0:
            return 0
        return 42
    return 0


def collection_type(some_sequence: list[Square] | list[int]) -> int:  # noqa: F405
    for foo in some_sequence:
        if isinstance(foo, Square):  # noqa: F405
            return 42
    return 0


def collection_type_in(some_sequence: dict[int, str] | list[int]) -> int:
    if 42 in some_sequence:
        return 42
    return 0


def type_from_comparison(a: Square) -> int | None:  # noqa: F405
    if a.a < 1000:
        return 0
    return None
