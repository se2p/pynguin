#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#

def foo(bar) -> bool:
    if bar == 42:
        return True
    assert bar is not None
    if bar == 24:
        return 1/0
    return False
