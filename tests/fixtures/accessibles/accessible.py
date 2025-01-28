#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#


class SomeType:
    def __init__(self, y: float):
        self._x = 5
        self._y = y

    def simple_method(self, x: int) -> float:
        return self._y * x * self._x


def simple_function(z: float) -> float:
    return z
