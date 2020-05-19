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
from typing import Iterator, List


class Foo:
    def __init__(self, a: List[int]) -> None:
        self._a = a

    def foo(self, x: int) -> int:
        return self._a[x]

    def __iter__(self) -> Iterator[int]:
        return iter(self._a)


class Bar(Foo):
    def foo(self, x: int) -> int:
        return self._a[x - 1]
