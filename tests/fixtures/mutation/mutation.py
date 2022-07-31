#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
from random import uniform


def foo(param) -> float:
    """This is flaky"""
    if param == 0:
        return uniform(5, 10)
    else:
        return 2.0
