#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import time


def timeout(foo):
    if foo == 2:
        time.sleep(4)
    return 5
