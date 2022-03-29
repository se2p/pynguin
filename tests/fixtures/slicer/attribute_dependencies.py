#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
# Idea and structure are taken from the pyChecco project, see:
# https://github.com/ipsw1/pychecco


class Foo:
    attr2 = [1, 2, 3]  # only this line of the class is included
    pass


def func():
    ob = Foo()  # not included in slice, since this has no effect on the result attribute
    ob.attr1 = 1
    ob.attr2 = ob.attr2.append(ob.attr1)

    result = ob.attr2
    return result

"""
  2           0 LOAD_GLOBAL              0 (Foo)
              2 CALL_FUNCTION            0
              4 STORE_FAST               0 (ob)

  3           6 LOAD_CONST               1 (1)
              8 LOAD_FAST                0 (ob)
             10 STORE_ATTR               1 (attr1)

  4          12 LOAD_FAST                0 (ob)
             14 LOAD_ATTR                2 (attr2)
             16 LOAD_METHOD              3 (append)
             18 LOAD_FAST                0 (ob)
             20 LOAD_ATTR                1 (attr1)
             22 CALL_METHOD              1
             24 LOAD_FAST                0 (ob)
             26 STORE_ATTR               2 (attr2)

  5          28 LOAD_FAST                0 (ob)
             30 LOAD_ATTR                2 (attr2)
             32 STORE_FAST               1 (result)

  6          34 LOAD_FAST                1 (result)
             36 RETURN_VALUE

"""
