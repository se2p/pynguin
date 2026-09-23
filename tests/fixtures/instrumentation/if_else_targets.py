#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#

def simple(x: int) -> int:
    if x > 0:
        y = 1
    else:
        y = 2
    return y

def nested(x: int, z: int) -> int:
    y = 0
    if x > 0:
        if z > 0:
            y = 1
        else:
            y = 2
    return y

def compound_and(x: int, z: int) -> int:
    if x > 0 and z > 0:
        return 1
    else:
        return 2

def compound_or(x: int, z: int) -> int:
    if x > 0 or z > 0:
        return 1
    else:
        return 2

def negated(x: bool) -> int:
    if not x:
        return 1
    else:
        return 2

def multi_line_condition(x: int, z: int) -> int:
    if (
        x > 0
        and z > 0
    ):
        return 1
    else:
        return 2

def elif_chain(x: int) -> int:
    if x > 10:
        return 1
    elif x > 5:
        return 2
    else:
        return 3

def else_with_loop(x: int, zs: list[int]) -> int:
    if x > 0:
        return x
    else:
        for z in zs:
            x += z
        return x

def else_with_single_if(x: int, z: int) -> int:
    if x > 0:
        return 1
    else:
        if z > 0:
            return 2
        else:
            return 3

def else_after_comment(x: int) -> int:
    if x > 0:
        return 1
    # the else header below is the target
    else:
        return 2

def else_with_pass(x: int) -> None:
    if x > 0:
        print(x)
    else:
        pass

def loop_else(zs: list[int]) -> int:
    for z in zs:
        if z > 0:
            break
    else:
        return 0
    return 1

def try_else(x: int) -> int:
    try:
        y = 10 // x
    except ZeroDivisionError:
        return 0
    else:
        return y

def else_body_no_cover(x: int) -> int:
    if x > 0:
        return 1
    else:
        return 2  # pynguin: no cover

def else_header_no_cover(x: int) -> int:
    if x > 0:
        return 1
    else:  # pynguin: no cover
        return 2

def for_else_no_break(xs: list[int]) -> int:
    total = 0
    for x in xs:
        total += x
    else:
        total = -total
    return total

def nested_for_else_no_break(a: int, xs: list[int]) -> int:
    if a > 0:
        for x in xs:
            a += x
        else:
            a = 7
    return a

def while_else_break(n: int) -> int:
    while n > 0:
        if n == 3:
            break
        n -= 1
    else:
        return 0
    return 1

def while_else_no_break(n: int) -> int:
    while n > 0:
        n -= 1
    else:
        n = 7
    return n

def loop_else_starts_with_loop(a: int, xs: list[int], ys: list[int]) -> int:
    if a > 0:
        for x in xs:
            a += x
        else:
            for y in ys:
                a -= y
    return a

def multi_line_for_else(xs: list[int]) -> int:
    for x in (
        xs
    ):
        if x > 0:
            break
    else:
        return 0
    return 1
