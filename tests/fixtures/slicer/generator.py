#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
# Idea and structure are taken from the pyChecco project, see:
# https://github.com/ipsw1/pychecco


def abc_generator():  # included in slice
    a = "a"  # included in slice
    b = "b"  # TODO(SiL) currently falsely included
    c = "c"  # TODO(SiL) currently falsely included
    yield a  # included in slice
    yield b  # TODO(SiL) currently falsely included
    yield c  # TODO(SiL) currently falsely included


def abc_xyz_generator():  # included in slice
    x = "x"  # included in slice
    y = "y"  # TODO(SiL) currently falsely included
    z = "z"  # TODO(SiL) currently falsely included

    yield from abc_generator()  # included in slice
    yield x  # included in slice
    yield y  # TODO(SiL) currently falsely included
    yield z  # TODO(SiL) currently falsely included


def func():
    generator = abc_xyz_generator()  # included in slice
    result = ""  # included in slice
    for letter in generator:  # included in slice
        if letter == "x" or letter == "a":  # included in slice
            result += letter  # included in slice
    return result
