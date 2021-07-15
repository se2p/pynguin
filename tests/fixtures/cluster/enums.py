#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
import enum


class Foo(enum.Enum):
    FOO = 1
    BAR = 2


class Color(enum.Flag):
    RED = enum.auto()
    BLUE = enum.auto()
    GREEN = enum.auto()


# Enum from functional API
Inline = enum.Enum("Inline", "YES NO MAYBE")
