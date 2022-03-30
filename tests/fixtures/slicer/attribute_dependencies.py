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


def func():
    ob = Foo()  # not included in slice, since this has no effect on the result attribute
    ob.attr1 = 1
    ob.attr2 = ob.attr2 + [ob.attr1]

    result = ob.attr2
    return result

