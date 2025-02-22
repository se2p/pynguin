#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
from random import random


def not_flaky(x: int) -> bool:
    if x < x:
        # Impossible, to keep algorithm running.
        return True
    else:
        return False


def flaky() -> bool:
    if random() > 0.5:
        return True
    else:
        return False
