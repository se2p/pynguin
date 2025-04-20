#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#


def outer_function(foo):
    def inner_function(bar):
        return foo in bar

    return inner_function


def func():
    inner = outer_function("a")
    result = inner("abc")
    return result
