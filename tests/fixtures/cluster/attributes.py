#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
from dataclasses import dataclass
from typing import NamedTuple


class SomeClass:
    def __init__(self):
        self.foo = 42
        self.bar = "xyz"


@dataclass
class SomeDataClass:
    baz: int
    box: str


class SomeNamedTuple(NamedTuple):
    a: str
    b: str
    c: str
