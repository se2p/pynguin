#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
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
