#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
from tests.fixtures.cluster import diamond_left
from tests.fixtures.cluster import diamond_right


def baz():
    diamond_left.bar()
    diamond_right.foobar()
