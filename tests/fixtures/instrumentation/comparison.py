#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
def _lt(x, y):
    if x < y:
        return True
    return False


def _le(x, y):
    if x <= y:
        return True
    return False


def _eq(x, y):
    if x == y:
        return True
    return False


def _ne(x, y):
    if x != y:
        return True
    return False


def _gt(x, y):
    if x > y:
        return True
    return False


def _ge(x, y):
    if x >= y:
        return True
    return False


def _in(x, y):
    if x in y:
        return True
    return False


def _not_in(x, y):
    if x not in y:
        return True
    return False


def _is(x, y):
    if x is y:
        return True
    return False


def _is_not(x, y):
    if x is not y:
        return True
    return False
