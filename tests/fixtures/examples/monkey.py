#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
from typing import Any


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
    def eat_bananas(number_bananas: int | float) -> int | float:
        print("I ate " + str(number_bananas) + " bananas")
        return number_bananas

    @staticmethod
    def all_my_stuff(items: list[Any]) -> None:
        items.append(" whoopsie daisy")
        for item in items:
            print("I own " + str(item))

    @property
    def name(self) -> str:
        return self._name
