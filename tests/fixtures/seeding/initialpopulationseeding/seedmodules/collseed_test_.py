#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import tests.fixtures.seeding.initialpopulationseeding.dummycontainer as module0


def seed_test_case0():
    var0 = [1, 2, 3]
    var1 = module0.i_take_list(var0)
    assert var1 == "not empty!"


def seed_test_case1():
    var0 = {1: "first", 2: "second", 3: "third"}
    var1 = module0.i_take_dict(var0)
    assert var1 == "not empty!"


def seed_test_case2():
    var0 = {1, 2, 3}
    var1 = module0.i_take_set(var0)
    assert var1 == "not empty!"


def seed_test_case3():
    var0 = (1, 2, 3)
    var1 = module0.i_take_tuple(var0)
    assert var1 == "not empty!"
