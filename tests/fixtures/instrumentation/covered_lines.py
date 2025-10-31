#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#

def no_cover_lines() -> int:
    a = 40
    print(a)  # pynguin: no cover

    b = 42
    if b > a:
        print(b)
    else:
        print(a)  # pynguin: no cover

    return 24

def no_cover_try_except(x: float, y: float) -> float:
    result = -1.0
    try:
        result = x / y
    except ZeroDivisionError:  # pynguin: no cover
        result = 0.0
    return result

def no_cover_try_finally(x: float, y: float) -> float:
    try:
        result = x / y
    finally:  # pynguin: no cover
        result = 0.0
    return result

def no_cover_try_except_else(x: float, y: float) -> float:
    result = -1.0
    try:
        result = x / y
    except ZeroDivisionError:
        result = 0.0
    else:  # pynguin: no cover
        result = 1.0
    return result

def no_cover_try_except_finally(x: float, y: float) -> float:
    result = -1.0
    try:
        result = x / y
    except ZeroDivisionError:
        result = 0.0
    finally:  # pynguin: no cover
        result = 1.0
    return result

def no_cover_try_except_else_finally(x: float, y: float) -> float:
    result = -1.0
    try:
        result = x / y
    except ZeroDivisionError:  # pynguin: no cover
        result = 0.0
    else:
        result = -1.0
    finally:
        result = 1.0
    return result
