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

  5          16 LOAD_FAST                2 (z)
             18 LOAD_CONST               3 (3)
             20 COMPARE_OP               2 (==)
             22 POP_JUMP_IF_TRUE        28
             24 LOAD_ASSERTION_ERROR
             26 RAISE_VARARGS            1
        >>   28 LOAD_CONST               0 (None)
             30 RETURN_VALUE
"""
