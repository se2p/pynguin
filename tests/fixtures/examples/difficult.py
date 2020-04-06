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


def difficult_branches(a: str, x: int, y: int) -> None:
    if x == 1337:
        if y == 42:
            print("Yes")
        else:
            print("No")

    if a == "a":
        if y == -1:
            print("Maybe")
        else:
            print("I don't know")

    if str(x) == a:
        print("Can you repeat the question?")
