#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later


def example(a: int, b: int, c: int) -> int:
    x = 0
    if a == b:
        if a > c:
            x = 1
        else:
            x = 2
    if b == c:
        x = -1
    return x
