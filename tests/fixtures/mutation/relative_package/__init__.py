#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2026 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
from . import helper


def foo(param: int) -> int:
    if param > 0:
        return helper.double(param)
    return 0
