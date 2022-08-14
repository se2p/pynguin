#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#


def outer_function(foo):
    def inner_function(bar):
        return foo in bar

    return inner_function


def func():
    inner = outer_function("a")
    result = inner("abc")
    return result
