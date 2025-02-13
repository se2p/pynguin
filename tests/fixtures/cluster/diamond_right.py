#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
from tests.fixtures.cluster.diamond_bottom import FooBar
from tests.fixtures.cluster.diamond_bottom import foo


def foobar():
    foo()
    FooBar()
