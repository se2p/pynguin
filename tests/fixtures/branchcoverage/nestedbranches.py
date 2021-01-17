#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#


def nested_branches(a: int) -> int:
    if a > 0:
        if a > 23:
            return 42
        return 23
    if a < -23:
        return -42
    return 0
