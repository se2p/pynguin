#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2022 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
from tests.fixtures.cluster.diamond_bottom import FooBar, foo


def bar():
    foo()
    FooBar()
