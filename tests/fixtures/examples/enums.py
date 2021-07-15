#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
import enum


class Foo(enum.Enum):
    BAR = 1
    BAZ = 2


def function(foo: Foo):
    print(f"Hi {foo.name}")
