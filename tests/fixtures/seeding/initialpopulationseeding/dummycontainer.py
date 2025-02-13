#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
from typing import Any


class Simple:
    def __init__(self, x: int):
        self._x = x

    def do_something(self, li: list) -> str:
        self._x = 10
        if len(li) > 0:
            return "not empty!"
        else:
            return "empty!"


def i_take_floats(f1: float, f2: float) -> str:
    if f1 == f2:
        return "Floats are equal!"
    else:
        return "Floats are different!"


def i_take_bools(b1: bool, b2: bool) -> str:
    if b1 == b2:
        return "Bools are equal!"
    else:
        return "Bools are different!"


def i_take_none(n: Any) -> str:
    if n is None:
        return "Is None!"
    else:
        return "Is not None!"


def i_take_strings(str1: str, str2: str) -> str:
    if str1 == str2:
        return "Strings are equal!"
    else:
        return "Strings are different!"


def i_take_list(li: list) -> str:
    if len(li) > 0:
        return "not empty!"
    else:
        return "empty!"


def i_take_dict(d: dict) -> str:
    if len(d) > 0:
        return "not empty!"
    else:
        return "empty!"


def i_take_set(s: set) -> str:
    if len(s) > 0:
        return "not empty!"
    else:
        return "empty!"


def i_take_tuple(t: tuple) -> str:
    if len(t) > 0:
        return "not empty!"
    else:
        return "empty!"


def i_take_bytes(b1: bytes, b2: bytes) -> str:
    if b1 == b2:
        return "Bytes are equal!"
    else:
        return "Bytes are different!"
