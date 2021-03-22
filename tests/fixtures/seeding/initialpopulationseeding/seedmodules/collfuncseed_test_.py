#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2021 Pynguin Contributors
#
#  SPDX-License-Identifier: LGPL-3.0-or-later
#
import tests.fixtures.seeding.initialpopulationseeding.dummycontainer as module0


def seed_test_case0():
    var0 = set()
    var1 = module0.i_take_set(s=var0)
    assert var1 == "empty!"


def seed_test_case1():
    var0 = list()
    var1 = module0.i_take_list(li=var0)
    assert var1 == "empty!"


def seed_test_case2():
    var0 = dict({1: "test"})
    var1 = module0.i_take_dict(d=var0)
    assert var1 == "not empty!"


def seed_test_case3():
    var0 = tuple([1, 2])
    var1 = module0.i_take_tuple(t=var0)
    assert var1 == "not empty!"


def seed_test_case4():
    var0 = tuple()
    var1 = module0.i_take_tuple(t=var0)
    assert var1 == "empty!"
