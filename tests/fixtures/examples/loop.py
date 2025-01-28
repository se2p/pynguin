#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
def here_goes_the_loop(f: int):
    x = True
    while x:
        if 3 * f != 70:
            x = False
    return x


def loop_with_condition():
    """Loops endlessly"""
    x = -1
    while x < 0:
        x = x - 1
