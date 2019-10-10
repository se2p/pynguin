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
from typing import Union, List, Any


class Monkey:
    def __init__(self, name: str) -> None:
        self._name = name

    def __str__(self) -> str:
        return self._name

    def __repr__(self) -> str:
        return self.__str__()

    def talk(self, sentence: str) -> "Monkey":
        print("I am a monkey, my name is " + self.__repr__() + " and I say " + sentence)
        return self

    def brother(self, monkey: "Monkey") -> "Monkey":
        if monkey.name == "John":
            string = monkey.name + " is not my brother"
        else:
            string = "My name is " + self._name + " and my brother is " + monkey._name
        print(string)
        return monkey

    @staticmethod
    def eat_bananas(number_bananas: Union[int, float]) -> Union[int, float]:
        print("I ate " + str(number_bananas) + " bananas")
        return number_bananas

    @staticmethod
    def all_my_stuff(items: List[Any]) -> None:
        items.append(" whoopsie daisy")
        for item in items:
            print("I own " + str(item))

    @property
    def name(self) -> str:
        return self._name
