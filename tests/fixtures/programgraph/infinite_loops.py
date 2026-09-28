#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#



def branchy_infinite_loop(x):
    while True:
        if x == 1:
            x += 1
        if x == 2:
            x += 1
        if x == 3:
            x += 1
        if x == 4:
            x += 1
        if x == 5:
            x += 1
        if x == 6:
            x += 1
        if x == 7:
            x += 1
        if x == 8:
            x += 1
        if x == 9:
            x += 1
        if x == 10:
            x += 1
        if x == 11:
            x += 1
        if x == 12:
            x += 1
        if x == 13:
            x += 1
        if x == 14:
            x += 1
        if x == 15:
            x += 1
        if x == 16:
            x += 1
        if x == 17:
            x += 1
        if x == 18:
            x += 1
        if x == 19:
            x += 1
        if x == 20:
            x += 1
        if x == 21:
            x += 1
        if x == 22:
            x += 1
        if x == 23:
            x += 1
        if x == 24:
            x += 1
        if x == 25:
            x += 1
        if x == 26:
            x += 1
        if x == 27:
            x += 1
        if x == 28:
            x += 1
        if x == 29:
            x += 1
        if x == 30:
            x += 1


def nested_infinite_loop(x):
    while True:
        while x > 0:
            x -= 1
        x += 10


def loop_reaching_infinite_loop(x):
    while True:
        x += 1
        if x > 10:
            break
    while True:
        x -= 1
