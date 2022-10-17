#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#


class Test:
    def __init__(self, value: int) -> None:
        self._value = value

    def test_method(self, x: int) -> int:
        return 5 * x


def a_test_function(x: float) -> float:
    return x * 5.5


def a_test_function_no_return() -> None:
    pass
