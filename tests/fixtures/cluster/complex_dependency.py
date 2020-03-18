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
from __future__ import annotations


class YetAnotherType:
    def __init__(self, arg0: int) -> None:
        pass

    def some_modifier(self, arg0: SomeOtherType) -> None:
        pass


class SomeOtherType:
    def __init__(self, arg0: YetAnotherType):
        pass

    def some_modifier(self, arg0: YetAnotherType) -> None:
        pass
