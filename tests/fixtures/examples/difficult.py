#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2023 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#


def difficult_branches(a: str, x: int, y: int) -> None:
    if x == 1337:
        if y == 42:
            print("Yes")
        else:
            print("No")

    if a == "a":
        if y == -1:
            print("Maybe")
        else:
            print("I don't know")

    if str(x) == a:
        print("Can you repeat the question?")
