#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2020 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#


def triangle(x: int, y: int, z: int) -> None:
    if x == y == z:
        print("Equilateral triangle")
    elif x == y or y == z or x == z:
        print("Isosceles triangle")
    else:
        print("Scalene triangle")
