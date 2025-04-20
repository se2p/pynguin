#  This file is part of Pynguin.
#
#  SPDX-FileCopyrightText: 2019–2025 Pynguin Contributors
#
#  SPDX-License-Identifier: MIT
#
import tests.fixtures.examples.triangle as module0


def seed_test_case_0():
    var0 = 10
    var1 = 20
    var2 = module0.triangle(var0, var1, var0)
    assert var2 == "Isosceles triangle"


def seed_test_case_1():
    var0 = -10
    var1 = 12
    var2 = module0.triangle(var0, var1, var1)
    assert var2 == "Scalene triangle"
