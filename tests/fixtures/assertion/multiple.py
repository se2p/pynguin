#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
# Idea and structure are taken from the pyChecco project, see:
# https://github.com/ipsw1/pychecco


def test_foo():
    x = 1
    y = 2
    z = x + y

    assert x == 1
    assert y == 2
    assert z == 3


"""
  2           0 LOAD_CONST               1 (1)
              2 STORE_FAST               0 (x)
  3           4 LOAD_CONST               2 (2)
              6 STORE_FAST               1 (y)
  4           8 LOAD_FAST                0 (x)
             10 LOAD_FAST                1 (y)
             12 BINARY_ADD
             14 STORE_FAST               2 (z)
  5          16 LOAD_FAST                0 (x)
             18 LOAD_CONST               1 (1)
             20 COMPARE_OP               2 (==)
             22 POP_JUMP_IF_TRUE        28

             24 LOAD_ASSERTION_ERROR
             26 RAISE_VARARGS            1

  6     >>   28 LOAD_FAST                1 (y)
             30 LOAD_CONST               2 (2)
             32 COMPARE_OP               2 (==)
             34 POP_JUMP_IF_TRUE        40

             36 LOAD_ASSERTION_ERROR
             38 RAISE_VARARGS            1

  7     >>   40 LOAD_FAST                2 (z)
             42 LOAD_CONST               3 (3)
             44 COMPARE_OP               2 (==)
             46 POP_JUMP_IF_TRUE        52

             48 LOAD_ASSERTION_ERROR
             50 RAISE_VARARGS            1

        >>   52 LOAD_CONST               0 (None)
             54 RETURN_VALUE
"""
