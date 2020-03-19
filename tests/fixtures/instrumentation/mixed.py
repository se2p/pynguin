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
"""A module that contains a mix of all possible functions"""
from tests.fixtures.instrumentation.inherited import SimpleClass, some_function


class TestClass(SimpleClass):
    # 1
    def __init__(self, x):
        self._x = x

    # 2
    def method(self, y):
        if self._x > y:
            return 0
        return 1

    # 3
    def method_with_nested(self, y):
        # 4
        def nested(x):
            if x > 5:
                return x + 1
            return 0

        if y == self._x:
            return nested(self._x)
        return 0


# 5
def generator():
    num = 0
    while num < 5:
        yield num
        num += 1


# 6
async def async_generator():
    num = 0
    while num < 5:
        yield num
        num += 1


# 7
async def coroutine(x):
    if x > 5:
        return 0
    return 1


# 8
def function(x):
    if x > 5:
        return 0
    return 1
