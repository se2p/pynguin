#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#

def not_covered1(x: int, y: int) -> int:  # pynguin: no cover
    if x > 0:
        return x
    else:
        return y

def not_covered2(  # pynguin: no cover
    x: int,
    y: int,
) -> int:
    return x + y

def not_covered3(  # pragma: no cover  # pynguin: no cover
    x: int,
    y: int,
    z: int
) -> int:
    return x * y * z

def covered(z: int) -> int:
    return z * 2
