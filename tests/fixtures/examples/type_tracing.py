#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
from tests.fixtures.examples.type_tracing_classes import *  # noqa: F403,F401


def try_to_test_me(a, b, c):
    if a.foo_96 > b.foo_30 + c:
        return 42
    return 0
