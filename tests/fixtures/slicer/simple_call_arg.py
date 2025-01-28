#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
# Idea and structure are taken from the pyChecco project, see:
# https://github.com/ipsw1/pychecco


def callee(a: int, b: int):
    # this line must not be included, since it has no effect on the result
    c = a + b  # noqa
    return a


def func():
    foo = 1  # must be included, is used by callee() and influences the result
    bar = 2  # currently included (I.D.D.); but a bit imprecise: used as parameter, but not in actual function
    result = callee(foo, bar)
    return result
