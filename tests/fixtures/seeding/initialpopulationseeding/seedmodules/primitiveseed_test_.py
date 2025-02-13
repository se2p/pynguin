#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import tests.fixtures.seeding.initialpopulationseeding.dummycontainer as module0


# Do not change the ordering of the testcases.


def seed_test_case0():
    var0 = 1.1
    var1 = 2.2
    var2 = module0.i_take_floats(var0, var1)
    assert var2 == "Floats are different!"


def seed_test_case1():
    var0 = -1.1
    var1 = -1.1
    var2 = module0.i_take_floats(var0, var1)
    assert var2 == "Floats are equal!"


def seed_test_case2():
    var0 = True
    var1 = True
    var2 = module0.i_take_bools(var0, var1)
    assert var2 == "Bools are equal!"


def seed_test_case3():
    var0 = not True
    var1 = not False
    var2 = module0.i_take_bools(var0, var1)
    assert var2 == "Bools are different!"


def seed_test_case4():
    var0 = None
    var1 = module0.i_take_none(var0)
    assert var1 == "Is None!"


def seed_test_case5():
    var0 = "First"
    var1 = "Second"
    var2 = module0.i_take_strings(var0, var1)
    assert var2 == "Strings are different!"


def seed_test_case6():
    var0 = b"rand_byte"
    var1 = b"another_rand_byte"
    var2 = module0.i_take_bytes(var0, var1)
    assert var2 == "Bytes are different!"
