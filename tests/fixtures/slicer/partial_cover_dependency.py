#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
# Idea and structure are taken from the pyChecco project, see:
# https://github.com/ipsw1/pychecco


class Foo:  # included in slice
    pass


def func():
    ob = Foo()  # included in slice, since this is the full explanation now
    ob.attr1 = (
        1  # partial cover (affects results, but not a full explanation for result)
    )

    result = ob  # included in slice
    return result
