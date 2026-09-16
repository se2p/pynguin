#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#


class SomeType:
    def __init__(self, y: float):
        self._x = 5
        self._y = y

    def simple_method(self, x: int) -> float:
        return self._y * x * self._x

    @classmethod
    def simple_classmethod(cls, x: int) -> float:
        return float(x * 2)

    @staticmethod
    def simple_staticmethod(x: int) -> float:
        return float(x * 3)

    async def simple_async_method(self, x: int) -> float:
        return self._y * x * self._x

    def simple_generator_method(self, x: int):
        yield self._y * x * self._x


def simple_function(z: float) -> float:
    return z


async def simple_async_function(z: float) -> float:
    return z


def simple_generator_function(z: float):
    yield z
