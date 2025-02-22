#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""A module that contains a mix of all possible functions"""
from tests.fixtures.instrumentation.inherited import SimpleClass


class TestClass(SimpleClass):
    # 1
    def __init__(self, x):
        self._x = x

    # 2
    def method(self, y):
        if self._x > y:
            return 0
        return 1

    # 3
    def method_with_nested(self, y):
        # 4
        def nested(x):
            if x > 5:
                return x + 1
            return 0

        if y == self._x:
            return nested(self._x)
        return 0


# 5
def generator():
    num = 0
    while num < 5:
        yield num
        num += 1


# 6
async def async_generator():
    num = 0
    while num < 5:
        yield num
        num += 1


# 7
async def coroutine(x):
    if x > 5:
        return 0
    return 1


# 8
def function(x):
    if x > 5:
        return 0
    return 1
