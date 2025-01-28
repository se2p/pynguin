#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
from time import sleep
from time import time_ns


def foo(param) -> float:
    """This is flaky"""
    if param == 0:
        # Will be different on each execution.
        sleep(0.1)
        return time_ns()
    else:
        return 2.0
