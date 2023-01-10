#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2023 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
from enum import Enum


class Foo(Enum):
    BAR = 1
    BAZ = 2


def function(foo: Foo):
    print(f"Hi {foo.name}")
