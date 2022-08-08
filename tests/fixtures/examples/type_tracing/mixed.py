#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
from tests.fixtures.examples.type_tracing.large_test_cluster import *  # noqa: F403,F401


def multiple_unknowns(a, b, c):
    if a.attribute_96 > b.attribute_30 + c:
        return 42
    return 0


def instance_check(x, y):
    some_list = [x]
    for foo in some_list:
        if isinstance(foo, Circle) and len(foo.r * y) > 100:  # noqa: F405
            return 42
    return 0


def only_args(*args):
    for v in args:
        if v.attribute_0:
            return 0
        return 42
    return 0


def only_kwargs(**kwargs):
    for v, k in kwargs.items():
        if k.attribute_0:
            return 0
        return 42
    return 0


def collection_type(some_list):
    for foo in some_list:
        if isinstance(foo, Square):  # noqa: F405
            return 42
    return 0


def collection_type_in(some_list):
    if 42 in some_list:
        return 42
    return 0


def type_from_comparison(a):
    if a.a < 1000:
        return 0
    return None
