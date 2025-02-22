#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#


def foo(a, b):
    return a - b


def bar(x: int, y, z) -> float:
    return foo(z, x) / y
