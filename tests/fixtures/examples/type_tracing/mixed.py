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
        if isinstance(foo, str) and len(foo * y) > 5:
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
        if foo:
            return 42
    return 0


def type_from_comparison(a):
    if a < 1000:
        return 0
    return None
