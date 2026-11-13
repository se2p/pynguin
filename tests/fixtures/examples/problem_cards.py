#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
"""One small callable per problem card type."""


def never_called(value: int) -> int:
    return value * 2


def sign(value: int) -> int:
    if value > 0:
        return 1
    return -1


class Account:
    def __init__(self, balance: int) -> None:
        if balance < 0:
            raise ValueError("negative balance")
        self.balance = balance

    def withdraw(self, amount: int) -> int:
        self.balance -= amount
        return self.balance


def nested(x: int, y: int) -> str:
    if x == 1337:
        if y > 0:
            return "positive"
        return "other"
    return "default"


def describe(value: int | str | None) -> str:
    if isinstance(value, str):
        return "text"
    if value is None:
        return "nothing"
    return "number"


def read_config(path: str) -> str:
    with open(path, encoding="utf-8") as file:  # noqa: PTH123
        return file.read()
