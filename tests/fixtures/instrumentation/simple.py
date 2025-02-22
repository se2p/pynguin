#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#


def simple_function(a):
    return a


def cmp_predicate(a, b):
    if a > b:
        return a
    else:
        return b


def bool_predicate(a):
    if a:
        return 1
    else:
        return 0


def for_loop(length: int):
    for x in range(length):
        return x


def full_for_loop(length: int):
    for x in range(length):
        print(x)


def multi_loop(x: int) -> int:
    the_sum = 0
    for i in range(x):
        for j in range(x):
            the_sum += 1
    for i in range(x - x):
        the_sum += 1
    return the_sum


def while_loop(length: int):
    while length > 0:
        print(length)
        length -= 1


def comprehension(y, z):
    return [x for x in range(y) if x != z]


def lambda_func(y):
    return lambda x: x + 1 if x > y else x


def conditional_assignment(x):
    y = 5 if x == 0 else 3
    return y


def conditionally_nested_class(x: int):
    if x > 5:

        class TestClass:
            def __init__(self):
                self.y = 3

        TestClass()


def explicit_none_return():
    print("This does nothing")
    return None
