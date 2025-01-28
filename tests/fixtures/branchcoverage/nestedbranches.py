#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#


def nested_branches(a: int) -> int:
    if a > 0:
        if a > 23:
            return 42
        return 23
    if a < -23:
        return -42
    return 0
