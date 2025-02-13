#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
# Idea and structure are taken from the pyChecco project, see:
# https://github.com/ipsw1/pychecco


def abc_generator():  # included in slice
    a = "a"  # included in slice
    b = "b"
    c = "c"
    yield a  # included in slice
    yield b
    yield c


def abc_xyz_generator():  # included in slice
    x = "x"  # included in slice
    y = "y"
    z = "z"

    yield from abc_generator()  # included in slice
    yield x  # included in slice
    yield y
    yield z


def func():
    generator = abc_xyz_generator()  # included in slice
    result = ""  # included in slice
    for letter in generator:  # included in slice
        if letter == "x" or letter == "a":  # included in slice
            result += letter  # included in slice
    return result
