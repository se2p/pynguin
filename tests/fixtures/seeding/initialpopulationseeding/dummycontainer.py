from typing import Any


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
