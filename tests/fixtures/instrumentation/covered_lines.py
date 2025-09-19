#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#

def no_cover_lines() -> int:
    a = 40
    print(a)  # pynguin: no cover

    b = 42
    if b > a:
        print(b)
    else:
        print(a)  # pynguin: no cover

    return 24
