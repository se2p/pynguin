#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#


def foo(x: int, y: int) -> int:
    if x == 0:
        if y == 0:
            return 42
        else:
            return 42 + y
    return -1
