# This file is part of Pynguin.
#
# Pynguin is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Pynguin is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with Pynguin.  If not, see <https://www.gnu.org/licenses/>.


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
