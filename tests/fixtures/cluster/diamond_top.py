#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2023 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
from tests.fixtures.cluster import diamond_left
from tests.fixtures.cluster import diamond_right


def baz():
    diamond_left.bar()
    diamond_right.foobar()
