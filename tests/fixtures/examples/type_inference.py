#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#


def foo(a, b):
    return a - b


def bar(x: int, y, z) -> float:
    return foo(z, x) / y
