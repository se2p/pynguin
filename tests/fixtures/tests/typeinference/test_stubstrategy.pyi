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
import typing
from typing import Tuple, Union

def typed_dummy(a: int, b: float, c) -> str: ...
def union_dummy(a: Union[int, float], b: Union[int, float]) -> Union[int, float]: ...
def return_tuple() -> Tuple[int, int]: ...

class TypedDummy:
    def __init__(self, a: typing.Any) -> None: ...
    def get_a(self) -> typing.Any: ...
