#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#

def no_cover_if(x: int, y: int) -> int:
    if x > 0:  # pynguin: no cover
        return x
    else:
        return y

def no_cover_elif(x: int, y: int) -> int:
    if x > 0:
        return x
    elif y > 0:  # pynguin: no cover
        return y
    else:
        return x

def no_cover_else(x: int, y: int) -> int:
    if x > 0:
        return x
    else:  # pynguin: no cover
        return y

def no_cover_nesting_if(x: int, y: int) -> int:
    if x > 0:  # pynguin: no cover
        if y > 0:
            return x
        else:
            return y
    else:
        return 0

def no_cover_nested_if(x: int, y: int) -> int:
    if x > 0:
        if y > 0:  # pynguin: no cover
            return x
        else:
            return y
    else:
        return 0

def no_cover_while(x: int) -> int:
    while x > 0:  # pynguin: no cover
        print(x)
    return x

def no_cover_if_in_while(x: int) -> int:
    while x > 0:  # pynguin: no cover
        if x > 0:
            print(x)
        else:
            print(-x)
    return x

def no_cover_for(x: int) -> int:
    for i in range(x):  # pynguin: no cover
        print(i)
    return x

def no_cover_for_else(x: int) -> int:
    for i in range(x):
        print(i)
    else:  # pynguin: no cover
        print(-1)
    return x
