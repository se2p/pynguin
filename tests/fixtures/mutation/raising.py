#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
def baz(foo: int) -> int:
    if foo > 0:
        raise ValueError
    return foo + 1
