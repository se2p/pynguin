#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
import tests.fixtures.seeding.initialpopulationseeding.dummycontainer as module0


class Example:
    pass


def seed_test_case0():
    var0 = 10
    var1 = module0.Simple(x=var0)
    var2 = var1.do_something(li=[1, 2, 3])
    assert var2 == "not empty!"
