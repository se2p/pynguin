#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
from enum import Enum


class Foo(Enum):
    BAR = 1
    BAZ = 2


def function(foo: Foo):
    print(f"Hi {foo.name}")
