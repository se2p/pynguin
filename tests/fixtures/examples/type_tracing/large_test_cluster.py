#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
# Simulate a large test cluster.
from dataclasses import dataclass

for _ in range(100):
    exec(
        f"""
class Foo{_}:
    attribute_{_} = {_}

    def __init__(self):
        pass


class Bar{_}:
    attribute_{_} = {100 - _}

    def __init__(self):
        pass"""
    )


@dataclass
class Square:
    a: float


@dataclass
class Circle:
    r: float


@dataclass
class Triangle:
    h: float
    b: float
