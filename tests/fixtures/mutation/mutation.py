#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2023 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
from time import sleep, time_ns


def foo(param) -> float:
    """This is flaky"""
    if param == 0:
        # Will be different on each execution.
        sleep(0.1)
        return time_ns()
    else:
        return 2.0
